import json
from enum import Enum, auto
from typing import Any, List, Optional, Tuple, Dict
from langchain_core.messages import BaseMessage

from pydantic import BaseModel, ValidationError, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from browser_use.browser.context import BrowserContext
from browser_use.browser.views import BrowserState
from browser_use.controller.service import Controller
from browser_use.agent.views import ActionResult, ActionModel

from common.utils import extract_json
from src.llm_models import LLMHub
from src.agent.custom_views import CustomAgentOutput, CustomAgentBrain
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
            agent_log.info(f"Completed plan item: {node.description}")

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

# TODO: find out what the hell this does
INCLUDE_ATTRIBUTES: List[str] = (
    ["title", "type", "name", "role", "aria-label", "placeholder", "value", "alt"]
)

# TODO List:
# - should add action for completing subgoals
# - update http listener and alert listener to wrap the pw context
# -> need to get bu.Context to return pw.context
# - terminate on success
# - add results from previous steps
# - find way to get the current url
# - before switching over to stagehand, we should build evaluations for perf comparing browser-base
# to stagehand
class AgentState(BaseModel):
    step: int
    max_steps: int
    is_done: bool = False

    def curr_step(self) -> int:
        """Always print 1-indexed"""
        return self.step + 1



# Wrapper classes for action and result to introduce a layer of indirection
# for when we potentially want to switch to stagehand
class AgentAction(BaseModel):
    action: ActionModel

    def __str__(self) -> str:
        return self.action.model_dump_json(exclude_unset=True)

class AgentResult(BaseModel):
    result: ActionResult

    @property
    def error(self) -> str:
        if self.result.error:
            return self.result.error.split('\n')[-1]
        return ""

    def __str__(self) -> str:
        return self.result.model_dump_json(exclude_unset=True)

class AgentStep(BaseModel):
    actions: List[AgentAction]
    results: List[AgentResult]
    current_state: CustomAgentBrain

class AgentContext:
    """The main interface for interacting agent step history"""
    def __init__(self, agent_steps: List[AgentStep]):
        self._ctxt = agent_steps

    def update(self, curr_actions: List[AgentAction], last_results: List[AgentResult], current_state: CustomAgentBrain) -> None:
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
                "current_state": ctxt.current_state.model_dump_json(),
                "actions": [a.model_dump_json() for a in ctxt.actions],
            }
            lines.append(history)
        return lines

    # @classmethod
    # def from_db(cls, agent_steps: List) -> "AgentContext":
    #     pass

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
        browser_context: BrowserContext,
        controller: Controller[Any],
        max_steps: int = 50,
        *,
        start_urls: Optional[List[str]] = None,
        page_max_steps: int = 10,
        http_capture: bool = False,
        cont_mode: bool = True
    ):
        self.task = start_task or NO_OP_TASK
        self.llm = llm
        self.browser_context = browser_context
        self.controller = controller
        self.cont_mode = cont_mode

        self.agent_context = AgentContext([])
        # TODO: check how url is updated in old code
        self.agent_state = AgentState(step=1, max_steps=max_steps, is_done=False)

        # TODO: deprecate and replace
        self.sys_prompt = agent_sys_prompt
        self.ActionModel = self.controller.registry.create_action_model()
        self.AgentOutput = CustomAgentOutput.type_with_custom_actions(self.ActionModel)

        # Optional HTTP capture hook
        self.http_handler = None
        self.http_history = None
        if http_capture and HAS_HTTP:
            # Only set handlers if available
            self.http_handler = HTTPHandler() if HTTPHandler else None
            self.http_history = HTTPHistory() if HTTPHistory else None
            if self.http_handler:
                self.browser_context.req_handler = self.http_handler.handle_request  # type: ignore[attr-defined]
                self.browser_context.res_handler = self.http_handler.handle_response  # type: ignore[attr-defined]

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

    async def _build_agent_prompt(self) -> List[dict[str, str]]:
        _, url, content = await self._get_browser_state()

        sys_msg = {
            "role": "system",
            "content": self.sys_prompt
        }
        agent_history = self.agent_context.history(self.agent_state.step)
        history = {
            "role": "user",
            "content": f"""
Here are the previous steps taken by the agent:
{agent_history}
""" 
        } if agent_history else {}

        agent_prompt = """
===== Current step: {step_number}/{max_steps} =====

Task: {task}
Current url: {curr_url}
Interactive Elements: {interactive_elements}
""".format(
    step_number=self.agent_state.curr_step(),
    max_steps=self.agent_state.max_steps,
    task=self.task, 
    curr_url=url, 
    interactive_elements=content
)
        agent_step = self.agent_context.prev_step()
        if agent_step:
            actions = agent_step.actions
            results = agent_step.results
            agent_prompt += "\n**Previous Actions**\n"
            agent_prompt += f'Previous step: {self.agent_state.curr_step() - 1}/{self.agent_state.max_steps} \n'
            for i, result in enumerate(results):
                action = actions[i]
                agent_prompt += f"Previous action {i + 1}/{len(results)}: {str(action)}\n"
                if result.error:
                    agent_prompt += (
                        f"Error of previous action {i + 1}/{len(results)}: ...{result.error}\n"
                    )
                    
        agent_msg = {
            "role": "user",
            "content": agent_prompt
        }

        return [msg for msg in [sys_msg, history, agent_msg] if msg]

    async def _execute_actions(
        self, ctx: BrowserContext, actions: List[Any]
    ) -> List[ActionResult]:
        """
        Minimal action runner. If your Controller differs, adapt here.
        """
        results: List[ActionResult] = []
        for action in actions:
            # Use Controller.act per upstream API
            res = await self.controller.act(
                action,
                ctx,
                page_extraction_llm=None,
                sensitive_data=None,
                available_file_paths=None,
                context=None,
            )
            results.append(res)
        return results

    def _check_done(self, results: List[ActionResult]) -> bool:
        # Check if any action was successful
        for result in results:
            if result.success:
                return True
        return False

    async def _get_browser_state(self) -> Tuple[BrowserState, str, str]:
        """
        1) Get browser state (the only state we truly need each turn).
        """
        browser_state = await self.browser_context.get_state()
        # this method calls into the pw browser
        page = await self.browser_context.get_current_page()
        url = page.url

        # Keep it simple: the LLM sees only a compact string of clickable elements
        content = browser_state.element_tree.clickable_elements_to_string(include_attributes=INCLUDE_ATTRIBUTES)
        return browser_state, url, content

    async def _llm_next_actions(
        self, input_messages: List[dict[str, str]]
    ) -> CustomAgentOutput:
        @retry(
            reraise=True,
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=2.0),
            retry=retry_if_exception_type(ValidationError),
        )
        def _invoke_and_parse() -> CustomAgentOutput:
            ai_msg: BaseMessage = self.llm.get("browser_use").invoke(input_messages)
            content = ai_msg.content
            if not isinstance(content, str):
                raise ValueError(f"Expected content to be a string, got {type(content)}")

            payload = json.loads(extract_json(content))
            return self.AgentOutput(**payload)  # type: ignore[return-value]

        parsed: CustomAgentOutput = _invoke_and_parse()
        return parsed

    def _update_state(self, model_output: CustomAgentOutput, results: List[ActionResult], *, new_url: str, new_page_contents: str) -> None:
        agent_actions = [AgentAction(action=a) for a in model_output.action]
        agent_results = [AgentResult(result=result) for result in results]

        self.agent_context.update(agent_actions, agent_results, model_output.current_state)
        self.agent_state.step += 1
        self.agent_state.is_done = self._check_done(results)

        # track prev values for planning
        self.prev_goal = model_output.current_state.next_goal
        self.eval_prev_goal = model_output.current_state.evaluation_previous_goal
        self.prev_url = new_url
        self.prev_page_contents = new_page_contents

    def _log_state(self, model_output: CustomAgentOutput, agent_msgs: List[dict[str, str]]) -> None:
        # log the agent prompt with DOM, prev acitons and results
        agent_log.info(agent_msgs[-1]["content"])

        success = "[Success]" if "Success" in model_output.current_state.evaluation_previous_goal else "[Failed]"
        agent_log.info(f"Eval {success}: {model_output.current_state.evaluation_previous_goal}")
        agent_log.info(f"Next Goal: {model_output.current_state.next_goal}")
        agent_log.info(f"Step {self.agent_state.step} completed")
        if self._plan is not None:
            agent_log.info(f"Current plan:\n{self._plan}")
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

    async def _nav_think(self, model_output: CustomAgentOutput, *, step_number: int) -> Event:
        eval_str = model_output.current_state.evaluation_previous_goal.lower()
        failed = ("failed" in eval_str) or ("unknown" in eval_str and step_number > 2)
        return Event.NAV_FAILED if failed else Event.NAV_SUCCESS

    async def _task_think(self, page_contents: str, url: str, *, step_number: int, model_output: CustomAgentOutput) -> Tuple[Optional[Event], Optional[str], Optional[PlanNode], Optional[NavPage]]:
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

    async def step(self):
        """
        One iteration:
          - read browser
          - build messages
          - query LLM
          - execute actions
        """
        # Build prompt for this turn
        agent_msgs = await self._build_agent_prompt()
        model_output = await self._llm_next_actions(agent_msgs)
        results = await self._execute_actions(self.browser_context, model_output.action)

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

        self._update_state(model_output, results, new_url=new_url, new_page_contents=new_page_contents)
        await self._transition(
            event=evt,
            new_url=new_url,
            new_page_contents=new_page_contents,
            new_plan=new_plan,
            new_task=new_task,
            nav_page=nav_page,
        )
        self._log_state(model_output, agent_msgs)
        
        # Optional: flush HTTP logs here if you wired http_capture
        # if self.http_handler and self.http_history:
        #     http_msgs = await self.http_handler.flush()
        #     filtered = self.http_history.filter_http_messages(http_msgs)
        #     _ = filtered  # do whatever you want with them

    async def run(self) -> None:
        while self.agent_state.step < self.agent_state.max_steps:
            await self.step()
            if self.agent_state.is_done and self.cont_mode:
                agent_log.info(f"Agent completed successfully @ {self.agent_state.step}/{self.agent_state.max_steps} steps!")
                break