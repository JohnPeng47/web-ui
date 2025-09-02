import json
from typing import Any, Dict, List, Optional, Tuple
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, ValidationError
from langchain_core.messages import BaseMessage

from browser_use.browser import BrowserSession
from browser_use.browser.views import BrowserStateSummary
from browser_use.controller.service import Controller
from browser_use.agent.views import ActionResult, AgentOutput
from browser_use.controller.registry.views import ActionModel
from browser_use.controller.views import NoParamsAction
from browser_use.agent.views import AgentBrain
from browser_use.dom.views import EnhancedDOMTreeNode

from src.agent.discovery.prompts.planv4 import (
    PlanItem,
    CreatePlanNested,
    UpdatePlanNestedV2 as UpdatePlanNested,
    CheckNestedPlanCompletion,
    TASK_PROMPT_WITH_PLAN,
)
from src.agent.links import parse_links_from_str
from src.agent.proxy import ProxyHandler
from src.llm_models import LLMHub
from src.agent.utils import url_did_change
from src.agent.pages import Page, PageObservations
from eval.client import PagedDiscoveryEvalClient

from common.utils import extract_json
from logger import get_agent_loggers

# Basic logger compatible with this repo
agent_log, full_log = get_agent_loggers()

# HTTP capture hooks from old architecture are not used with the new BrowserSession
NO_OP_TASK = "Do nothing unless necessary. If a popup appears, dismiss it. Then emit done."

INCLUDE_ATTRIBUTES: List[str] = (
    ["title", "type", "name", "role", "aria-label", "placeholder", "value", "alt"]
)
EMPTY_MSG = {"role": "user", "content": ""}

class GoToUrlAction(BaseModel):
    url: str
    new_tab: bool

class GoToUrlActionModel(ActionModel):
    go_to_url: GoToUrlAction | None = None

class GoBackActionModel(ActionModel):
    go_back: NoParamsAction | None = None

class LLMNextActionsError(Exception):
    def __init__(self, message: str, errors: list[dict[str, str]]):
        super().__init__(message)
        self.errors = errors

# TODO List:
# - refactor: clean up browser-use operations and move them out of this implementation

# - terminate on success
# - add results from previous steps
# - find way to get the current url
# - before switching over to stagehand, we should build evaluations for perf
#   comparing browser-use to stagehand
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

class HistoryItem(BaseModel, ABC):
    step: int

    @abstractmethod
    def to_history_item(self) -> dict[str, Any]:
        pass

class AgentStep(HistoryItem):
    actions: List[Any]
    results: List[ActionResult]
    current_state: Any # For some reason cant use AgentBrain annotation here?

    def to_history_item(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "actions": [a.model_dump_json() for a in self.actions],
            "results": [r.model_dump_json() for r in self.results],
            "current_state": self.current_state.model_dump_json(),
        }

class Event(HistoryItem):
    msg: str

    def to_history_item(self) -> dict[str, Any]:
        return {
            "msg": self.msg,
        }

class AgentContext:
    """The main interface for interacting agent step history"""
    def __init__(self, agent_steps: List[HistoryItem]):
        self._ctxt = agent_steps

    def update(self, step: int, curr_actions: List[ActionModel], last_results: List[ActionResult], current_state: AgentBrain) -> None:
        curr_step = AgentStep(
            step=step, 
            actions=curr_actions, 
            results=last_results, 
            current_state=current_state
        )
        prev_step = self.prev_agent_step()
        if prev_step:
            prev_step.results.extend(last_results)
        self._ctxt.append(curr_step)

    # TODO: unify this API with update()
    def update_event(self, step: int, msg: str):
        self._ctxt.append(Event(step=step, msg=msg))

    def steps(self) -> List[HistoryItem]:
        return self._ctxt

    def prev_agent_step(self) -> AgentStep | None:
        if not self._ctxt:
            return None
        # Find the latest AgentStep by iterating backwards
        for item in reversed(self._ctxt):
            if isinstance(item, AgentStep):
                return item
        return None

    def history(self, end_step: Optional[int] = None) -> List[dict[str, Dict]]:
        lines = []
        for i, ctxt in enumerate(self._ctxt[:end_step], start = 1):
            lines.append(ctxt.to_history_item())
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
        llm: LLMHub,
        agent_sys_prompt: str,
        browser_session: BrowserSession,
        controller: Controller,
        start_urls: List[str],
        max_steps: int = 50,
        max_page_steps: int = 10,
        *,
        challenge_client: Optional[PagedDiscoveryEvalClient] = None,
        proxy_handler: ProxyHandler | None = None,
        agent_dir: Path,
        init_task: Optional[str] = None,
        screenshots: bool = False
    ):
        # initiailized in the agent loop
        # self.task = ""
        self.take_screenshot = screenshots
        self.llm = llm
        self.browser_session = browser_session
        self.controller = controller
        self.agent_context = AgentContext([])
        self.agent_state = AgentState(step=1, max_steps=max_steps, is_done=False)
        self.agent_dir = agent_dir
        self.proxy_handler = proxy_handler
        self.challenge_client = challenge_client

        self._init_task = init_task

        # System prompt and schema for actions
        self.sys_prompt = agent_sys_prompt
        # Include all actions (unfiltered) in the schema; we will filter in text prompts
        # Controller has the registry; use it to build the ActionModel
        self.ActionModel = self.controller.registry.create_action_model(page_url=None)
        self.AgentOutput = AgentOutput.type_with_custom_actions(self.ActionModel)

        # TODO: MOVE INTO AGENT_CONTEXT
        self.urls = start_urls
        self.max_page_steps = max_page_steps
        self.page_skip = False
        self.pages: PageObservations = PageObservations()
        self.page_step = 0
        self.plan: PlanItem | None = None
        self.curr_dom_tree: EnhancedDOMTreeNode | None = None
        self.curr_url: str = ""
        self.curr_dom_str: str = ""

        if self.take_screenshot:
            self._set_screenshot_service()

    def _set_screenshot_service(self) -> None:
        """Initialize screenshot service using agent directory"""
        try:
            from browser_use.screenshots.service import ScreenshotService

            self.screenshot_service = ScreenshotService(self.agent_dir)
            self._log(f'📸 Screenshot service initialized in: {self.agent_dir}/screenshots')
        except Exception as e:
            self._log(f'📸 Failed to initialize screenshot service: {e}.')
            raise 

    async def _build_agent_prompt(self) -> List[Any]:
        # Combine provided system prompt with available actions description
        try:
            actions_description = self.controller.registry.get_prompt_description(page_url=None)
        except Exception:
            actions_description = ""

        sys_text = f"{self.sys_prompt}\n\nYour AVAILABLE ACTIONS:\n{actions_description}"
        sys_msg = {
            "role": "system",
            "content": sys_text,
        }

        agent_history = self.agent_context.history(self.agent_state.step)
        history_msg = (
            {
                "role": "user",
                "content": "Here are the previous steps taken by the agent:\n" + json.dumps(agent_history),
            }
            if agent_history
            else EMPTY_MSG
        )

        agent_prompt = (
            "Current step: {step_number}/{max_steps}\n\n"
            "Task: {task}\n"
            "Current url: {curr_url}\n"
            "Interactive Elements: {interactive_elements}\n"
        ).format(
            step_number=self.agent_state.curr_step(),
            max_steps=self.agent_state.max_steps,
            task=self.task,
            curr_url=self.curr_url,
            interactive_elements=self.curr_dom_str,
        )
        agent_step = self.agent_context.prev_agent_step()
        if agent_step:
            actions = agent_step.actions
            results = agent_step.results
            agent_prompt += "\n**Previous Actions**\n"
            agent_prompt += f"Previous step: {self.agent_state.curr_step() - 1}/{self.agent_state.max_steps} \n"
            for i, result in enumerate(results):
                action = actions[i]
                agent_prompt += f"Previous action {i + 1}/{len(results)}: {str(action)}\n"
                if result.error:
                    agent_prompt += (
                        f"Error of previous action {i + 1}/{len(results)}: ...{result.error}\n"
                    )

        agent_msg = {
            "role": "user",
            "content": agent_prompt,
        }
        return [sys_msg, history_msg, agent_msg]

    async def _curr_page_check(self) -> bool:
        """Checks check if we accidentally went to a new page before officially transitioning and go back if so"""
        # TODO: try to cache calls to this method and track url change with every call
        state = await self.browser_session.get_browser_state_summary(
            cache_clickable_elements_hashes=True,
            include_screenshot=False,
            cached=False,
            include_recent_events=False,
        )
        # TODO_IMPORTANT: need to change this back to support regular URL checking after juice_shop 
        # > removing check page updates for now 
        if url_did_change(self.curr_url, state.url):
            self._log(f"Page changed from {self.curr_url} to {state.url}, going back")

            await asyncio.sleep(self.browser_session.browser_profile.wait_between_actions)
            res = await self.controller.act(
                action=GoBackActionModel(**{"go_back": NoParamsAction()}),
                browser_session=self.browser_session,
                page_extraction_llm=None,
                sensitive_data=None,
                available_file_paths=None,
                file_system=None,  # pass a real FileSystem if you use done() attachments
                context=None,
            )
            agent_log.info(f"[Action]: {GoBackActionModel(**{'go_back': NoParamsAction()})}")
            agent_log.info(f"[Result]: {res}")

            self.agent_context.update_event(
                self.agent_state.step, 
                f"[GO_BACK] Page changed from {self.curr_url} to {state.url}, going back"
            )
            return True
        return False

    # TODO: replace with method that piggybacks off of dom_str
    async def _get_page_html(self) -> str:
        # Ensure the session is started and connected
        cdp_session = await self.browser_session.get_or_create_cdp_session()
        result = await cdp_session.cdp_client.send.Runtime.evaluate(
            params={
                "expression": "document.documentElement.outerHTML",
                "returnByValue": True,
            },
            session_id=cdp_session.session_id,
        )
        return result["result"]["value"]
    
    async def _update_plan(self, new_dom_str: str):
        """
        Updates the plan based on changes to the DOM tree 
        """
        if not self.plan:
            raise ValueError("Plan is not initialized")
        
        updated_plan = UpdatePlanNested().invoke(
            model=self.llm.get("update_plan"),
            prompt_args={
                "plan": self.plan,
                "curr_page_contents": self.curr_dom_str,
                "prev_page_contents": new_dom_str,
            },
            prompt_logger=full_log,
        )
        # TODO: should only update if we have different plans
        self._update_plan_and_task(updated_plan)
        self._find_links_on_page()

    async def _check_plan_complete(self, new_dom_str: str):
        """
        Checks if the plan is complete by comparing the new DOM tree to the plan
        """
        if not self.plan:
            raise ValueError("Plan is not initialized")
        
        completed = CheckNestedPlanCompletion().invoke(
            model=self.llm.get("check_plan_completion"),
            prompt_args={
                "plan": self.plan,
                "prev_page_contents": self.curr_dom_str,
                "curr_page_contents": new_dom_str,
                "curr_goal": self.agent_context.prev_agent_step().current_state.next_goal,
            },
            prompt_logger=full_log,
        )
        for compl in completed.plan_indices:
            node = self.plan.get(compl)
            if node is not None:
                node.completed = True
                agent_log.info(f"[COMPLETE_PLAN_ITEM]: {node.description}")
            else:
                agent_log.info(f"PLAN_ITEM_NOT_COMPLETED")
        
        self._update_plan_and_task(self.plan)

    def _update_plan_and_task(self, plan: PlanItem):
        self.plan = plan
        self.task = TASK_PROMPT_WITH_PLAN.format(plan=str(self.plan))

    # UGLY
    async def _goto_page(self, url: str):
        res = await self.controller.act(
            action=GoToUrlActionModel(**{"go_to_url": GoToUrlAction(url=url, new_tab=False)}),
            browser_session=self.browser_session,
            page_extraction_llm=None,
            sensitive_data=None,
            available_file_paths=None,
            file_system=None,  # pass a real FileSystem if you use done() attachments
            context=None,
        )
        await asyncio.sleep(self.browser_session.browser_profile.wait_between_actions)

        agent_log.info(f"[Action]: {GoToUrlActionModel(**{'go_to_url': GoToUrlAction(url=url, new_tab=False)})}")
        agent_log.info(f"[Result]: {res}")

        self.agent_context.update_event(
            self.agent_state.step, 
            f"[GOTO_PAGE] Go to url: {url}"
        )

    # UGLY
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
                        break

                    # Also bail if new elements appeared (D``OM shape changed)
                    new_hashes = {e.parent_branch_hash() for e in new_map.values()}
                    if not new_hashes.issubset(cached_hashes):
                        msg = f"New elements appeared after action {i}/{len(actions)}; stopping remaining actions."
                        results.append(ActionResult(extracted_content=msg, include_in_memory=True, long_term_memory=msg))
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

            agent_log.info(f"[Action]: {action}")
            agent_log.info(f"[Result]: {res}")

            if res.is_done or res.error:
                break

        return results

    def _find_links_on_page(self):
        """Manually scrape links in the DOM string"""
        if not self.curr_dom_tree:
            raise ValueError("Current DOM tree is not initialized!")

        links = parse_links_from_str(self.curr_dom_tree.to_str())
        for link in links:
            agent_log.info(f"Discovered additional link: {link}")
            self.pages.curr_page().add_link(link)

    def _create_new_plan(self):
        new_plan = CreatePlanNested().invoke(
            model=self.llm.get("create_plan"),
            prompt_args={
                "curr_page_contents": self.curr_dom_str,
            },
            prompt_logger=full_log
        )
        self._update_plan_and_task(new_plan)
        self._find_links_on_page()

        # needed so that the next eval step doesnt fail
        self.agent_context.update_event(
            self.agent_state.step, 
            f"[NEW_PAGE] Forced browsing to go to {self.curr_url}, you should ignore the result of executing the next action"
        )

    def _check_done(self, results: List[ActionResult]) -> bool:
        # New API: Done indicated via is_done flag
        return any(getattr(result, "is_done", False) for result in results)

    async def _get_browser_state(self) -> BrowserStateSummary:
        """
        1) Get browser state summary (the only state we truly need each turn).
        """
        browser_state: BrowserStateSummary = await self.browser_session.get_browser_state_summary(
            include_screenshot=True,
            cached=False,
            include_recent_events=False,
        )
        return browser_state

    # UGLY
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

    # TODO: consider moving out single task execution logic into a subclass 
    async def step(self):
        """
        One iteration:
          - read browser
          - build messages
          - query LLM
          - execute actions
        """
        # 1) Create plan if this is the first step we take on the page
        if self.page_step == 0:
            self._log(f"[PAGE_TRANSITION]: {self.curr_url}")

            self.curr_url = self.urls.pop(0)
            await self._goto_page(self.curr_url)
            self.pages.add_page(Page(url=self.curr_url))

            browser_state = await self._get_browser_state()
            self.curr_dom_str = browser_state.dom_state.llm_representation(include_attributes=INCLUDE_ATTRIBUTES)
            self.curr_dom_tree = browser_state.dom_tree

            if not self._init_task:
                self._create_new_plan()
            else:
                self.task = self._init_task
        try:
            agent_msgs = await self._build_agent_prompt()
            model_output = await self._llm_next_actions(agent_msgs)
            results = await self._execute_actions(model_output.action)
            # this action can potentially invalidate the last agent action
            if not self._init_task:
                new_page = await self._curr_page_check()
                if new_page:
                    return
        except Exception as e:
            self._handle_error(e)
            self.agent_state.is_done = True
            return

        # 3) Everything after this relies on new agent state as result of executed action
        # new browser state after executing actions
        new_browser_state = await self._get_browser_state()
        new_dom = new_browser_state.dom_state.llm_representation(include_attributes=INCLUDE_ATTRIBUTES)

        await self._update_state(new_browser_state, model_output, results)

        if not self._init_task:
            # TODO: move these into update_state
            await self._check_plan_complete(new_dom)
            await self._update_plan(new_dom)

        self._log_state(model_output, agent_msgs)
        
        # update page state
        if self.proxy_handler:
            msgs = await self.proxy_handler.flush()
            for msg in msgs:
                self.pages.curr_page().add_http_msg(msg)
            if self.challenge_client:
                await self.challenge_client.update_status(
                    msgs, 
                    self.curr_url, 
                    self.agent_state.step, 
                    self.page_step,
                )

    async def run(self) -> None:
        while self.agent_state.step < self.agent_state.max_steps:
            await self.step()
            if self.agent_state.is_done:
                self._log(f"Agent completed successfully @ {self.agent_state.curr_step()}/{self.agent_state.max_steps} steps!")
                break

            self.agent_state.step += 1
            self.page_step += 1
            if self.page_step > self.max_page_steps:
                self.page_step = 0
                
    # State update and logging 
    def _log(self, msg: str):
        agent_log.info(msg)
        full_log.info(msg)

    def _handle_error(self, e: Exception):
        if isinstance(e, LLMNextActionsError):
            self._log(f"LLMNextActionsError: {e.errors}")
        else:
            import traceback
            self._log(f"Error in step, skipping to next step")
            self._log(f"Stack trace: {traceback.format_exc()}")

    async def _update_state(self, browser_state: BrowserStateSummary, model_output: AgentOutput, results: List[ActionResult]) -> None:
        self.curr_dom_str = browser_state.dom_state.llm_representation(include_attributes=INCLUDE_ATTRIBUTES)
        self.curr_dom_tree = browser_state.dom_tree
        self.agent_context.update(self.agent_state.step, model_output.action, results, model_output.current_state)
        self.agent_state.is_done = self._check_done(results)

        if browser_state.screenshot and self.take_screenshot:
            self._log(
                f'📸 Storing screenshot for step {self.agent_state.step}, screenshot length: {len(browser_state.screenshot)}'
            )
            screenshot_path = await self.screenshot_service.store_screenshot(browser_state.screenshot, self.agent_state.step)
            self._log(f'📸 Screenshot stored at: {screenshot_path}')
        else:
            self._log(f'📸 No screenshot in browser_state_summary for step {self.agent_state.step}')

    def _log_state(self, model_output: AgentOutput, agent_msgs: List[Any]) -> None:
        self._log(f"========== Agent State: {self.agent_state.curr_step()}/{self.agent_state.max_steps} ==========")
        
        full_log.info("[HISTORY]")
        for msg in agent_msgs[:-1]:
            full_log.info(msg["content"])
        self._log(agent_msgs[-1]["content"])

        success_prefix = "[Success]" if (model_output.current_state.evaluation_previous_goal or "").lower().find("success") != -1 else "[Failed]"
        self._log(f"Eval {success_prefix}: {model_output.current_state.evaluation_previous_goal}")
        self._log(f"Next Goal: {model_output.current_state.next_goal}")
        self._log(f"Step {self.agent_state.step} completed")

    async def _write_dom_tree(self, browser_state: BrowserStateSummary):
        dom_node = browser_state.dom_tree
        with open(f"dom_tree_{self.agent_state.step}.json", "w") as f:
            f.write(json.dumps(dom_node.__json__()))