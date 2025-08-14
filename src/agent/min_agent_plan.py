import json
from enum import Enum, auto
from typing import Any, List, Optional, Tuple, Dict
from langchain_core.messages import BaseMessage
import asyncio

from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryCallState
from browser_use.browser import BrowserSession
from browser_use.browser.views import BrowserStateSummary
from browser_use.controller.service import Controller
from browser_use.agent.views import ActionResult, AgentOutput
from browser_use.controller.registry.views import ActionModel

from common.utils import extract_json
from src.llm_models import LLMHub
from src.agent.utils import Pages
from src.agent.discovery import (
    CreatePlanNested,
    UpdatePlanNested,
    CheckNestedPlanCompletion,
    CompletedNestedPlanItem,
    DetermineNewPage,
    NewPageStatus,
    NavPage,
    TASK_PROMPT_WITH_PLAN,
)
from src.agent.discovery.prompts.planv3 import PlanItem as PlanNode
from eval.client import PagedDiscoveryEvalClient

from pentest_bot.logger import get_agent_loggers

agent_log, full_log = get_agent_loggers()

# Optional: keep HTTP capture hook if you actually use it
try:
    from .http_history import HTTPHistory, HTTPHandler  # noqa
    HAS_HTTP = True
except Exception:
    HTTPHistory = None  # type: ignore[assignment]
    HTTPHandler = None  # type: ignore[assignment]
    HAS_HTTP = False

class AgentMode(Enum):
    NAVIGATION = auto()
    TASK_EXECUTION = auto()
    START_ACTION = auto()


class Event(Enum):
    NAV_START = auto()
    NAV_SUCCESS = auto()
    NAV_FAILED = auto()
    TASK_COMPLETE = auto()
    BACKTRACK = auto()
    PAGE_COMPLETE = auto()
    SHUTDOWN = auto()


TRANSITIONS: Dict[Tuple[AgentMode, Event], AgentMode] = {
    (AgentMode.START_ACTION, Event.NAV_START): AgentMode.NAVIGATION,
    (AgentMode.TASK_EXECUTION, Event.NAV_START): AgentMode.NAVIGATION,
    (AgentMode.TASK_EXECUTION, Event.BACKTRACK): AgentMode.NAVIGATION,
    (AgentMode.TASK_EXECUTION, Event.PAGE_COMPLETE): AgentMode.NAVIGATION,
    (AgentMode.NAVIGATION, Event.NAV_FAILED): AgentMode.NAVIGATION,
    (AgentMode.NAVIGATION, Event.NAV_SUCCESS): AgentMode.TASK_EXECUTION,
}


class EarlyShutdown(Exception):
    pass

NO_OP_TASK = """
This is a no-op task. The agent will not take any action
Actually, if there are popups on the page, dismiss them

Make sure to:
- automatically evaluate this current task as successful by the next agentic step
Emit the done action to mark this no-op task as completed
"""

NAVIGATE_TO_PAGE_PROMPT = """
Here is the current page contents:
{curr_page_contents}

Navigate to the following page using the goto action. You *MUST* take the goto action:
{url}

Put as your next goal: Come up with a plan for the new page
EVALUATION NOTE: the URL may have been redirected, so just just judging by the success of the URL is not enough
to determine if navigation was successful
"""

async def _create_or_update_plan(
    llm: LLMHub,
    curr_page_contents: str,
    curr_url: str,
    step_number: int,
    *,
    prev_page_contents: str,
    prev_url: str,
    eval_prev_goal: str,
    curr_goal: str,
    curr_plan: PlanNode,
    homepage_contents: str,
    homepage_url: str,
) -> Tuple[Optional["Event"], Optional[str], PlanNode, PlanNode, Optional[NavPage]]:
    """Lifted planning helper adapted for MinimalAgent.

    Returns (event, new_task, updated_plan, old_plan, nav_page).
    """
    new_task: Optional[str] = None
    event: Optional["Event"] = None
    old_plan: PlanNode = curr_plan

    completed: CompletedNestedPlanItem = CheckNestedPlanCompletion().invoke(
        model=llm.get("check_plan_completion"),
        prompt_args={
            "plan": curr_plan,
            "prev_page_contents": prev_page_contents,
            "curr_page_contents": curr_page_contents,
            "curr_goal": curr_goal,
        },
        prompt_logger=full_log,
    )
    for compl in completed.plan_indices:
        node = curr_plan.get(compl)
        if node is not None:
            node.completed = True
            agent_log.info(f"[COMPLETE_PLAN_ITEM]: {node.description}")
        else:
            agent_log.info(f"PLAN_ITEM_NOT_COMPLETED")

    nav_page: NavPage = DetermineNewPage().invoke(
        model=llm.get("determine_new_page"),
        prompt_args={
            "curr_page_contents": curr_page_contents,
            "prev_page_contents": prev_page_contents,
            "curr_url": curr_url,
            "prev_url": prev_url,
            "curr_goal": curr_goal,
            "homepage_contents": homepage_contents,
            "homepage_url": homepage_url,
        },
        prompt_logger=full_log,
    )
    if nav_page.status == NewPageStatus.NEW_PAGE:
        agent_log.info(f"Discovered [new_page]: {curr_url}")
        agent_log.info(f"Navigating back to homepage:{homepage_url}")
        new_task = NAVIGATE_TO_PAGE_PROMPT.format(
            curr_page_contents=curr_page_contents, url=homepage_url
        )
        event = Event.BACKTRACK
    elif nav_page.status == NewPageStatus.SUBPAGE:
        agent_log.info(f"Discovered [subpage]: {nav_page.name}")
        curr_plan = UpdatePlanNested().invoke(
            model=llm.get("update_plan"),
            prompt_args={
                "plan": curr_plan,
                "curr_page_contents": curr_page_contents,
                "prev_page_contents": prev_page_contents,
                "curr_goal": curr_goal,
            },
            prompt_logger=full_log,
        )
        new_task = TASK_PROMPT_WITH_PLAN.format(plan=curr_plan)
    else:
        agent_log.info("No task updates")

    return event, new_task, curr_plan, old_plan, nav_page

class LLMNextActionsError(Exception):
    def __init__(self, message: str, errors: list[dict[str, str]]):
        super().__init__(message)
        self.errors = errors

INCLUDE_ATTRIBUTES: List[str] = (
    ["title", "type", "name", "role", "aria-label", "placeholder", "value", "alt"]
)

# TODO List:
# - store http messages for replayability
class AgentState(BaseModel):
    step: int
    max_steps: int
    is_done: bool = False

    def curr_step(self) -> int:
        """Always print 1-indexed"""
        return self.step + 1

# Wrapper classes for action and result to introduce a layer of indirection
# for when we potentially want to switch to stagehand
class AgentStep(BaseModel):
    actions: List[Any]
    results: List[ActionResult]
    current_state: Any

class AgentContext:
    """The main interface for interacting agent step history"""
    def __init__(self, agent_steps: List[AgentStep]):
        self._ctxt = agent_steps

    def update(self, curr_actions: List[ActionModel], last_results: List[ActionResult], current_state: Any) -> None:
        
        curr_step = AgentStep(actions=curr_actions, results=last_results, current_state=current_state)
        prev_step = self.prev_step()
        if prev_step:
            prev_step.results.extend(last_results)
        self._ctxt.append(curr_step)

    def steps(self) -> List[AgentStep]:
        return self._ctxt

    def prev_step(self) -> AgentStep | None:
        if not self._ctxt:
            return None
        return self._ctxt[-1]

    def history(self, end_step: Optional[int] = None) -> List[dict[str, Dict]]:
        lines = []
        for i, ctxt in enumerate(self._ctxt[:end_step], start = 1):
            history = {
                "step": i,
                "current_state": json.dumps(ctxt.current_state.model_dump() if hasattr(ctxt.current_state, "model_dump") else getattr(ctxt.current_state, "__dict__", {})),
                "actions": [a.model_dump_json() for a in ctxt.actions],
            }
            lines.append(history)
        return lines

    # @classmethod
    # def from_db(cls, agent_steps: List) -> "AgentContext":
    #     pass

def build_agent_prompt(
    *,
    sys_prompt: str,
    task: str,
    curr_url: str,
    interactive_elements: str,
    curr_step: int,
    max_steps: int,
    agent_history: Optional[List[Dict]] = None,
    prev_actions: Optional[List[Any]] = None,
    prev_results: Optional[List[Any]] = None,
) -> List[dict[str, str]]:
    """Build the LLM prompt for the agent.

    This is a pure function that formats the system/user messages given
    the current browser state, step counters, and optional history.
    """
    sys_msg = {
        "role": "system",
        "content": sys_prompt,
    }

    history_msg: dict[str, str] = {}
    if agent_history:
        history_msg = {
            "role": "user",
            "content": (
                """
Here are the previous steps taken by the agent:
{agent_history}
"""
            ).format(agent_history=agent_history),
        }

    agent_prompt = (
        """
===== Current step: {step_number}/{max_steps} =====

Task: {task}
Current url: {curr_url}
Interactive Elements: {interactive_elements}
"""
    ).format(
        step_number=curr_step,
        max_steps=max_steps,
        task=task,
        curr_url=curr_url,
        interactive_elements=interactive_elements,
    )

    if prev_actions and prev_results:
        agent_prompt += "\n**Previous Actions**\n"
        agent_prompt += f"Previous step: {curr_step - 1}/{max_steps} \n"
        for i, result in enumerate(prev_results):
            action = prev_actions[i]
            agent_prompt += f"Previous action {i + 1}/{len(prev_results)}: {str(action)}\n"
            # Expect prev_results to expose an 'error' attribute or falsy value
            err = getattr(result, "error", "")
            if err:
                agent_prompt += (
                    f"Error of previous action {i + 1}/{len(prev_results)}: ...{err}\n"
                )

    agent_msg = {
        "role": "user",
        "content": agent_prompt,
    }

    return [msg for msg in [sys_msg, history_msg, agent_msg] if msg]

class MinimalAgent:
    """
    Minimal agent:
      step():
        1) get_browser_state
        2) get_next_action (LLM)
        3) execute actions
      run(): repeats step() up to max_steps

    Everything else is a hook you can wire back in if you truly need it.
    """

    def __init__(
        self,
        start_task: str,
        llm: LLMHub,
        agent_sys_prompt: str,
        browser_session: BrowserSession,
        controller: Controller,
        max_steps: int = 50,
        *,
        start_urls: Optional[List[str]] = None,
        page_max_steps: int = 10,
        http_capture: bool = False,
        cont_mode: bool = True,
        # TODO: remove this annotation
        challenge_client: Optional[PagedDiscoveryEvalClient] = None
    ):
        self.task = start_task or NO_OP_TASK
        self.llm = llm
        self.browser_session = browser_session
        self.controller = controller
        self.cont_mode = cont_mode
        self.challenge_client = challenge_client

        self.agent_context = AgentContext([])
        # TODO: check how url is updated in old code
        self.agent_state = AgentState(step=1, max_steps=max_steps, is_done=False)

        # TODO: deprecate and replace
        self.sys_prompt = agent_sys_prompt
        self.ActionModel = self.controller.registry.create_action_model(page_url=None)
        self.AgentOutput = AgentOutput.type_with_custom_actions(self.ActionModel)

        # Optional HTTP capture hook
        self.http_handler = None
        self.http_history = None
        # HTTP capture hooks from old architecture are not used with the new BrowserSession
        if http_capture and HAS_HTTP:
            self.http_handler = HTTPHandler() if HTTPHandler else None
            self.http_history = HTTPHistory() if HTTPHistory else None

        # ---------------- planning state ---------------- #
        self.mode: AgentMode = AgentMode.START_ACTION
        self.pages: Pages = Pages(items=start_urls or [])
        self.subpages: List[str] = []
        self._backtrack: bool = False
        self._replace_plan: Optional[PlanNode] = None
        self._plan: Optional[PlanNode] = None

        self.homepage_url: str = ""
        self.homepage_contents: str = ""

        # previous-step tracking
        self.prev_goal: str = ""
        self.eval_prev_goal: str = ""
        self.prev_url: str = ""
        self.prev_page_contents: str = ""

        # per-page step tracking
        self.page_step_number: int = 0
        self.page_max_steps: int = page_max_steps

    # Removed unused DOM link extraction to align with new BrowserSession API
    async def _build_agent_prompt(self) -> List[dict[str, str]]:
        _, url, content = await self._get_browser_state()

        agent_step = self.agent_context.prev_step()
        prev_actions = agent_step.actions if agent_step else None
        prev_results = agent_step.results if agent_step else None

        messages = build_agent_prompt(
            sys_prompt=self.sys_prompt,
            task=self.task,
            curr_url=url,
            interactive_elements=content,
            curr_step=self.agent_state.curr_step(),
            max_steps=self.agent_state.max_steps,
            agent_history=self.agent_context.history(self.agent_state.step),
            prev_actions=prev_actions,
            prev_results=prev_results,
        )

        return messages

    async def _execute_actions(self, actions: List[Any]) -> List[ActionResult]:
        results: List[ActionResult] = []
        baseline = await self.browser_session.get_browser_state_summary(
            cache_clickable_elements_hashes=True,
            include_screenshot=False,
            cached=False,
            include_recent_events=False,
        )
        cached_selector_map = baseline.dom_state.selector_map
        cached_hashes = {e.parent_branch_hash() for e in cached_selector_map.values()}

        for i, action in enumerate(actions):
            # 2) Between-actions: let UI settle and re-sync DOM
            agent_log.info(f"Executing action {i}/{len(actions)}: {action.model_dump_json()}")
            if i > 0:
                await asyncio.sleep(self.browser_session.browser_profile.wait_between_actions)
                state = await self.browser_session.get_browser_state_summary(
                    cache_clickable_elements_hashes=False,
                    include_screenshot=False,
                    cached=False,
                    include_recent_events=False,
                )
                new_map = state.dom_state.selector_map

                idx = getattr(action, "get_index", lambda: None)()
                if idx is not None:
                    orig = cached_selector_map.get(idx)
                    new = new_map.get(idx)
                    orig_hash = orig.parent_branch_hash() if orig else None
                    new_hash = new.parent_branch_hash() if new else None

                    # If the target moved or vanished, stop to replan next step
                    if orig_hash != new_hash:
                        msg = f"Element index changed after action {i}/{len(actions)}, stopping to replan."
                        results.append(ActionResult(extracted_content=msg, include_in_memory=True, long_term_memory=msg))
                        agent_log.info(msg)
                        break

                    # Also bail if new elements appeared (DOM shape changed)
                    new_hashes = {e.parent_branch_hash() for e in new_map.values()}
                    if not new_hashes.issubset(cached_hashes):
                        msg = f"New elements appeared after action {i}/{len(actions)}; stopping remaining actions."
                        results.append(ActionResult(extracted_content=msg, include_in_memory=True, long_term_memory=msg))
                        agent_log.info(msg)
                        break

            res = await self.controller.act(
                action=action,
                browser_session=self.browser_session,
                page_extraction_llm=None,
                sensitive_data=None,
                available_file_paths=None,
                file_system=None,  # pass a real FileSystem if you use done() attachments
                context=None,
            )
            results.append(res)

            if res.is_done or res.error:
                break

        return results

    def _check_done(self, results: List[ActionResult]) -> bool:
        return any(getattr(result, "is_done", False) or getattr(result, "success", False) for result in results)

    async def _get_browser_state(self) -> Tuple[BrowserStateSummary, str, str]:
        """
        1) Get browser state summary (the only state we truly need each turn).
        """
        browser_state: BrowserStateSummary = await self.browser_session.get_browser_state_summary(
            include_screenshot=False,
            cached=False,
            include_recent_events=False,
        )
        url = browser_state.url
        content = browser_state.dom_state.llm_representation(include_attributes=INCLUDE_ATTRIBUTES)
        return browser_state, url, content

    async def _llm_next_actions(
        self, input_messages: List[dict[str, str]]
    ) -> AgentOutput:
        error_outputs: list[dict[str, Any]] = []
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            content: Optional[str] = None
            payload: Optional[dict[str, Any]] = None

            try:
                # If your .invoke(...) is async, replace with: ai_msg = await ...
                ai_msg: BaseMessage = self.llm.get("browser_use").invoke(input_messages)
                content = ai_msg.content
                if not isinstance(content, str):
                    raise ValueError(f"Expected content to be a string, got {type(content)}")

                payload = json.loads(extract_json(content))

                # This is the line you care about: track per-payload failures here.
                agent_output = self.AgentOutput(**payload)  # type: ignore[call-arg]
                agent_log.info("AGENT OUTPUT: %s", content)
                return agent_output

            except (ValidationError, TypeError) as e:
                # Pydantic or typing errors when building AgentOutput(**payload)
                error_entry = {
                    "attempt": attempt,
                    "stage": "model_parse",
                    "exception": type(e).__name__,
                    "message": str(e),
                    "payload": payload,          # keep the exact payload that failed
                    "raw_content": content,
                }
                error_outputs.append(error_entry)
                agent_log.error("Attempt %s model_parse failed: %s", attempt, e)

            # Backoff between attempts, then loop
            if attempt < max_attempts:
                await asyncio.sleep(min(2.0, 0.5 * (2 ** (attempt - 1))))

        # Exhausted all attempts
        agent_log.error("Aggregate LLM parse failures: %s", error_outputs)
        raise LLMNextActionsError(
            "Failed to produce a valid AgentOutput after retries.",
            error_outputs,
        )
    def _update_state(self, model_output: AgentOutput, results: List[ActionResult], *, new_url: str, new_page_contents: str) -> None:
        self.agent_context.update(model_output.action, results, model_output.current_state)
        self.agent_state.step += 1
        self.agent_state.is_done = self._check_done(results)

        # track prev values for planning
        self.prev_goal = model_output.current_state.next_goal
        self.eval_prev_goal = model_output.current_state.evaluation_previous_goal
        self.prev_url = new_url
        self.prev_page_contents = new_page_contents

    def _log_state(self, model_output: AgentOutput, agent_msgs: List[dict[str, str]]) -> None:
        # log the agent prompt with DOM, prev acitons and results
        agent_log.info("Post Action DOM: \n" + agent_msgs[-1]["content"])

        success_prefix = "[Success]" if (model_output.current_state.evaluation_previous_goal or "").lower().find("success") != -1 else "[Failed]"
        agent_log.info(f"Eval {success_prefix}: {model_output.current_state.evaluation_previous_goal}")
        agent_log.info(f"Next Goal: {model_output.current_state.next_goal}")
        agent_log.info(f"Step {self.agent_state.step} completed")
        if self.pages:
            agent_log.info(f"Pages: {self.pages}")

    # ---------------- planning helpers ---------------- #
    def _set_plan(self, plan: PlanNode) -> None:
        full_log.info(f"[NEW PLAN]:\n{plan}")
        self._plan = plan

    def _get_plan(self) -> Optional[PlanNode]:
        return self._plan

    def _set_task(self, task: str, *, is_new_task: bool = False) -> None:  # noqa: ARG002
        self.task = task

    def _get_task(self) -> str:
        return self.task

    async def _nav_think(self, model_output: AgentOutput, *, step_number: int) -> Event:
        eval_str = model_output.current_state.evaluation_previous_goal.lower()
        failed = ("failed" in eval_str) or ("unknown" in eval_str and step_number > 2)
        return Event.NAV_FAILED if failed else Event.NAV_SUCCESS

    async def _task_think(self, page_contents: str, url: str, *, step_number: int, model_output: AgentOutput) -> Tuple[Optional[Event], Optional[str], Optional[PlanNode], Optional[NavPage]]:
        curr_plan = self._get_plan()
        if curr_plan is None:
            raise EarlyShutdown("No plan found, should not happen")

        event, new_task, new_plan, old_plan, nav_page = await _create_or_update_plan(
            llm=self.llm,
            curr_page_contents=page_contents,
            curr_url=url,
            step_number=step_number,
            prev_page_contents=self.prev_page_contents,
            prev_url=self.prev_url,
            eval_prev_goal=model_output.current_state.evaluation_previous_goal,
            curr_goal=model_output.current_state.next_goal,
            curr_plan=curr_plan,
        homepage_contents=self.homepage_contents,
            homepage_url=self.homepage_url,
        )
        if event == Event.BACKTRACK:
            self._backtrack = True
            self._replace_plan = old_plan

        return event, new_task, new_plan, nav_page

    async def _transition(
        self,
        *,
        event: Optional[Event],
        new_url: str,
        new_page_contents: str,
        new_plan: Optional[PlanNode] = None,
        new_task: Optional[str] = None,
        nav_page: Optional[NavPage] = None,
    ) -> None:
        if event is None:
            agent_log.info(f"No transition staying in {self.mode}")
            if self.mode is AgentMode.TASK_EXECUTION and new_task:
                self._set_task(new_task, is_new_task=False)
                if new_plan is not None:
                    self._set_plan(new_plan)
                if nav_page:
                    self.subpages.append(nav_page.name)
            next_mode = self.mode
        else:
            next_mode = TRANSITIONS.get((self.mode, event), self.mode)
            agent_log.info(f"{self.mode} -[{event}]-> {next_mode}")
            self.mode = next_mode
            if next_mode is AgentMode.NAVIGATION:
                if event in [Event.NAV_START, Event.PAGE_COMPLETE]:
                    # TODO: put spider links into here
                    target = self.pages.pop()
                    agent_log.info(f"Starting at new page: {target}")
                    task = NAVIGATE_TO_PAGE_PROMPT.format(
                        curr_page_contents=new_page_contents,
                        url=target,
                    )
                    self._set_task(task, is_new_task=True)
                    if event == Event.PAGE_COMPLETE:
                        agent_log.info(f"[PAGE] Page transition to {target} complete")
                        self.page_step_number = 0
                        self._backtrack = False
                elif event == Event.BACKTRACK:
                    self.pages.add(new_url)
                    if new_task:
                        self._set_task(new_task, is_new_task=True)
            elif next_mode is AgentMode.TASK_EXECUTION:
                if event == Event.NAV_SUCCESS:
                    self.homepage_url = new_url
                    self.homepage_contents = new_page_contents
                    if not self._backtrack:
                        agent_log.info("Creating new plan")
                        created_plan: PlanNode = CreatePlanNested().invoke(
                            model=self.llm.get("create_plan"),
                            prompt_args={"curr_page_contents": new_page_contents},
                            prompt_logger=full_log,
                        )
                        self._set_plan(created_plan)
                        new_task = TASK_PROMPT_WITH_PLAN.format(plan=created_plan)
                        self._set_task(new_task, is_new_task=True)
                    else:
                        agent_log.info("Backtracking, replacing plan with original")
                        if self._replace_plan is not None:
                            self._set_plan(self._replace_plan)
                            new_task = TASK_PROMPT_WITH_PLAN.format(plan=self._replace_plan)
                            self._set_task(new_task, is_new_task=True)

        self.mode = next_mode

    def _handle_error(self, e: Exception):
        if isinstance(e, LLMNextActionsError):
            agent_log.info(f"LLMNextActionsError: {e.errors}")
            return
        else:
            import traceback
            agent_log.info(f"Error in step, skipping to next step")
            agent_log.info(f"Stack trace: {traceback.format_exc()}")
            return

    async def step(self):
        """
        One iteration:
          - read browser
          - build messages
          - query LLM
          - execute actions
        """
        try:
            # Build prompt for this turn
            agent_msgs = await self._build_agent_prompt()
            model_output = await self._llm_next_actions(agent_msgs)
            results = await self._execute_actions(model_output.action)
        # TODO: should have better error handling 
        # but works for now, because we can return and go next step without agent updating
        except Exception as e:
            self._handle_error(e)

        # fetch new browser state for planning decisions
        _, new_url, new_page_contents = await self._get_browser_state()

        # compute transition event
        evt: Optional[Event] = None
        new_task: Optional[str] = None
        new_plan: Optional[PlanNode] = None
        nav_page: Optional[NavPage] = None

        # increment per-page step counter
        self.page_step_number += 1

        if self.mode == AgentMode.START_ACTION and self._check_done(results):
            agent_log.info("START ACTION COMPLETED!")
            evt = Event.NAV_START
        else:
            if self.page_step_number >= self.page_max_steps:
                evt = Event.PAGE_COMPLETE
            else:
                if self.mode == AgentMode.NAVIGATION:
                    evt = await self._nav_think(model_output, step_number=self.agent_state.step)
                elif self.mode == AgentMode.TASK_EXECUTION:
                    evt, new_task, new_plan, nav_page = await self._task_think(
                        new_page_contents,
                        new_url,
                        step_number=self.agent_state.step,
                        model_output=model_output,
                    )

        self._update_state(
            model_output, 
            results, 
            new_url=new_url, 
            new_page_contents=new_page_contents
        )
        # Optional: flush HTTP logs here if you wired http_capture
        if self.http_handler and self.http_history:
            http_msgs = await self.http_handler.flush()
            filtered = self.http_history.filter_http_messages(http_msgs)
            if self.challenge_client:
                completed = self.challenge_client.update_status(filtered, new_url)
                if completed is None:
                    agent_log.info("No yet on challenge page")
                else:
                    if completed == 1:
                        agent_log.info("CHALLENGE COMPLETED!!")
                        self.cont_mode = True
                        return

        await self._transition(
            event=evt,
            new_url=new_url,
            new_page_contents=new_page_contents,
            new_plan=new_plan,
            new_task=new_task,
            nav_page=nav_page,
        )
        self._log_state(model_output, agent_msgs)
        
    async def run(self) -> None:
        while self.agent_state.step < self.agent_state.max_steps:
            await self.step()
            if self.agent_state.is_done and self.cont_mode:
                agent_log.info(f"Agent completed successfully @ {self.agent_state.step}/{self.agent_state.max_steps} steps!")
                break
        
        if self.challenge_client:
            complete, complete_str = self.challenge_client.report_progress()
            agent_log.info(f"[Challenge Status]: {complete_str}")

        agent_log.info(f"Cost: {json.dumps(self.llm.get_costs(), indent=2)}")