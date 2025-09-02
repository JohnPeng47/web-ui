import json
from typing import Any, Dict, List, Optional
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

from src.llm_models import LLMHub
from common.utils import extract_json
from logger import get_agent_loggers
from src.agent.proxy import ProxyHandler
from eval.client import PagedDiscoveryEvalClient

# Basic logger compatible with this repo
agent_log, full_log = get_agent_loggers()

# Attributes to include in DOM string representations
INCLUDE_ATTRIBUTES: List[str] = [
    "title",
    "type",
    "name",
    "role",
    "aria-label",
    "placeholder",
    "value",
    "alt",
]

EMPTY_MSG = {"role": "user", "content": ""}


# ----------------------------
# History / Context structures
# ----------------------------
class AgentAction(BaseModel):
    action: ActionModel

    def __str__(self) -> str:
        return self.action.model_dump_json(exclude_unset=True)


class AgentResult(BaseModel):
    result: ActionResult

    @property
    def error(self) -> str:
        if self.result.error:
            return self.result.error.split("\n")[-1]
        return ""

    def __str__(self) -> str:
        return self.result.model_dump_json(exclude_unset=True)


class HistoryItem(BaseModel, ABC):
    step: int

    @abstractmethod
    def to_history_item(self) -> Dict[str, Any]:
        pass


class AgentStep(HistoryItem):
    actions: List[Any]
    results: List[ActionResult]
    current_state: Any

    def to_history_item(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "actions": [a.model_dump_json() for a in self.actions],
            "results": [r.model_dump_json() for r in self.results],
            "current_state": self.current_state.model_dump_json(),
        }


class Event(HistoryItem):
    msg: str

    def to_history_item(self) -> Dict[str, Any]:
        return {"msg": self.msg}


class AgentContext:
    """Simple interface for recording step history."""

    def __init__(self, agent_steps: List[HistoryItem]):
        self._ctxt = agent_steps

    def update(
        self,
        step: int,
        curr_actions: List[ActionModel],
        last_results: List[ActionResult],
        current_state: Any,
    ) -> None:
        curr_step = AgentStep(
            step=step,
            actions=curr_actions,
            results=last_results,
            current_state=current_state,
        )
        prev_step = self.prev_agent_step()
        if prev_step:
            prev_step.results.extend(last_results)
        self._ctxt.append(curr_step)

    def update_event(self, step: int, msg: str) -> None:
        self._ctxt.append(Event(step=step, msg=msg))

    def steps(self) -> List[HistoryItem]:
        return self._ctxt

    def prev_agent_step(self) -> Optional[AgentStep]:
        if not self._ctxt:
            return None
        for item in reversed(self._ctxt):
            if isinstance(item, AgentStep):
                return item
        return None

    def history(self, end_step: Optional[int] = None) -> List[Dict[str, Dict[str, Any]]]:
        lines: List[Dict[str, Dict[str, Any]]] = []
        for ctxt in self._ctxt[: end_step if end_step is not None else None]:
            lines.append(ctxt.to_history_item())
        return lines


# ----------------------------
# Agent state
# ----------------------------
class AgentState(BaseModel):
    step: int
    max_steps: int
    is_done: bool = False

    def curr_step(self) -> int:
        return self.step + 1


# ----------------------------
# Errors
# ----------------------------
class LLMNextActionsError(Exception):
    def __init__(self, message: str, errors: List[Dict[str, Any]]):
        super().__init__(message)
        self.errors = errors


# ----------------------------
# Stepped Simple Agent (no planning, no navigation orchestration)
# ----------------------------
class SimpleAgent:
    """
    Stepped agent that executes a single TASK across multiple steps with the classic
    run()/step() loop. There is no plan creation or update, no link parsing, and no
    automatic navigation logic. The TASK string never changes between steps.

    Each step:
      1) Read current browser state
      2) Build prompt from static TASK + DOM
      3) Ask LLM for actions
      4) Execute actions (with DOM-shift guardrails)
      5) Update state and log
    """

    def __init__(
        self,
        task: str,
        llm: LLMHub,
        agent_sys_prompt: str,
        browser_session: BrowserSession,
        controller: Controller,
        *,
        eval_client: Optional[PagedDiscoveryEvalClient] = None,
        proxy_handler: Optional[ProxyHandler] = None,
        agent_dir: Path,
        max_steps: int = 50,
        wait_between_steps: float = 0.0,
    ):
        self.task = task.strip()
        self.llm = llm
        self.browser_session = browser_session
        self.controller = controller
        self.agent_context = AgentContext([])
        self.agent_state = AgentState(step=1, max_steps=max_steps, is_done=False)
        self.sys_prompt = agent_sys_prompt
        self.wait_between_steps = wait_between_steps
        self.proxy_handler = proxy_handler
        self.eval_client = eval_client

        # Action schema pulled directly from registry
        self.ActionModel = self.controller.registry.create_action_model(page_url=None)
        self.AgentOutput = AgentOutput.type_with_custom_actions(self.ActionModel)

        # Minimal persistent state
        self.curr_url: str = ""
        self.curr_dom_str: str = ""

        self._set_screenshot_service(agent_dir)

    # ------------
    # Setup
    # ------------
    def _set_screenshot_service(self, agent_dir: Path) -> None:
        try:
            from browser_use.screenshots.service import ScreenshotService

            self.screenshot_service = ScreenshotService(agent_dir)
            self._log(f"Screenshot service initialized in: {agent_dir}/screenshots")
        except Exception as e:
            self._log(f"Failed to initialize screenshot service: {e}.")
            raise

    # ------------
    # Prompting
    # ------------
    async def _build_agent_prompt(self) -> List[Dict[str, str]]:
        try:
            actions_description = self.controller.registry.get_prompt_description(page_url=None)
        except Exception:
            actions_description = ""

        sys_text = (
            f"{self.sys_prompt}\\n\\n"
            f"You are executing a single TASK across multiple steps. Do not modify the TASK. "
            f"Avoid explicit navigation actions unless absolutely necessary for the TASK, and call done() when complete.\\n\\n"
            f"AVAILABLE ACTIONS:\\n{actions_description}"
        )
        sys_msg = {"role": "system", "content": sys_text}

        agent_history = self.agent_context.history(self.agent_state.step)
        history_msg = (
            {"role": "user", "content": "Previous steps:\\n" + json.dumps(agent_history)}
            if agent_history
            else EMPTY_MSG
        )

        agent_prompt = (
            "Current step: {step_number}/{max_steps}\\n\\n"
            "TASK: {task}\\n"
            "Current url: {curr_url}\\n"
            "Interactive Elements: {interactive_elements}\\n"
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
            agent_prompt += "\\n**Previous Actions**\\n"
            agent_prompt += (
                f"Previous step: {self.agent_state.curr_step() - 1}/{self.agent_state.max_steps} \\n"
            )
            for i, result in enumerate(results):
                action = actions[i]
                agent_prompt += f"Previous action {i + 1}/{len(results)}: {str(action)}\\n"
                if result.error:
                    agent_prompt += (
                        f"Error of previous action {i + 1}/{len(results)}: ...{result.error}\\n"
                    )

        agent_msg = {"role": "user", "content": agent_prompt}
        return [sys_msg, history_msg, agent_msg]

    # ------------
    # Browser
    # ------------
    async def _get_browser_state(self) -> BrowserStateSummary:
        return await self.browser_session.get_browser_state_summary(
            include_screenshot=True,
            cached=False,
            include_recent_events=False,
        )

    # ------------
    # Execution
    # ------------
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

                    if orig_hash != new_hash:
                        msg = (
                            f"Element index changed after action {i}/{len(actions)}, stopping to replan."
                        )
                        results.append(
                            ActionResult(
                                extracted_content=msg,
                                include_in_memory=True,
                                long_term_memory=msg,
                            )
                        )
                        break

                    new_hashes = {e.parent_branch_hash() for e in new_map.values()}
                    if not new_hashes.issubset(cached_hashes):
                        msg = (
                            f"New elements appeared after action {i}/{len(actions)}; stopping remaining actions."
                        )
                        results.append(
                            ActionResult(
                                extracted_content=msg,
                                include_in_memory=True,
                                long_term_memory=msg,
                            )
                        )
                        break

            res = await self.controller.act(
                action=action,
                browser_session=self.browser_session,
                page_extraction_llm=None,
                sensitive_data=None,
                available_file_paths=None,
                file_system=None,
                context=None,
            )
            results.append(res)

            agent_log.info(f"[Action]: {action}")
            agent_log.info(f"[Result]: {res}")

            if res.is_done or res.error:
                break

        return results

    async def _llm_next_actions(self, input_messages: List[Dict[str, str]]) -> AgentOutput:
        error_outputs: List[Dict[str, Any]] = []
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            content: Any = None
            payload: Optional[Dict[str, Any]] = None

            try:
                ai_msg: BaseMessage = self.llm.get("browser_use").invoke(input_messages)
                content = ai_msg.content
                if not isinstance(content, str):
                    raise ValueError(f"Expected content to be a string, got {type(content)}")

                payload = json.loads(extract_json(content))
                agent_output = self.AgentOutput(**payload)  # type: ignore[call-arg]
                agent_log.info("AGENT OUTPUT: %s", content)
                return agent_output

            except (ValidationError, TypeError) as e:
                error_entry = {
                    "attempt": attempt,
                    "stage": "model_parse",
                    "exception": type(e).__name__,
                    "message": str(e),
                    "payload": payload,
                    "raw_content": content,
                }
                error_outputs.append(error_entry)
                agent_log.error("Attempt %s model_parse failed: %s", attempt, e)

            if attempt < max_attempts:
                await asyncio.sleep(min(2.0, 0.5 * (2 ** (attempt - 1))))

        agent_log.error("Aggregate LLM parse failures: %s", error_outputs)
        raise LLMNextActionsError(
            "Failed to produce a valid AgentOutput after retries.", error_outputs
        )

    # ------------
    # Step/run API
    # ------------
    async def step(self) -> None:
        """One iteration of read → prompt → act → update."""
        # 1) Read current browser state
        browser_state = await self._get_browser_state()
        self.curr_url = browser_state.url
        self.curr_dom_str = browser_state.dom_state.llm_representation(
            include_attributes=INCLUDE_ATTRIBUTES
        )

        # 2) Build messages
        agent_msgs = await self._build_agent_prompt()

        # 3) LLM for next actions
        try:
            model_output = await self._llm_next_actions(agent_msgs)
        except Exception as e:
            self._handle_error(e)
            self.agent_state.is_done = True
            return

        # 4) Execute actions
        results = await self._execute_actions(model_output.action)

        # 5) Update state
        new_state = await self._get_browser_state()
        await self._update_state(new_state, model_output, results)
        self._log_state(model_output, agent_msgs)

        # Finish if any action signaled done or an error occurred
        if self._check_done(results):
            self.agent_state.is_done = True

        if self.proxy_handler:
            msgs = await self.proxy_handler.flush()
            for msg in msgs:
                agent_log.info(f"[{msg.method}] {msg.url}")

                if self.eval_client:
                    agent_log.info(f"[{self.curr_url}]")
                    completed = await self.eval_client.update_status(msgs, self.curr_url)
                    if completed is None:
                        agent_log.info("No yet on challenge page")
                    else:
                        if completed == 1:
                            agent_log.info("CHALLENGE COMPLETED!!")
                            # self.agent_state.is_done = True
                            return

    async def run(self) -> None:
        while self.agent_state.step < self.agent_state.max_steps:
            await self.step()
            if self.agent_state.is_done:
                self._log(
                    f"Agent completed @ {self.agent_state.curr_step()}/{self.agent_state.max_steps} steps."
                )
                break

            self.agent_state.step += 1
            if self.wait_between_steps:
                await asyncio.sleep(self.wait_between_steps)

    # ------------
    # Helpers
    # ------------
    def _check_done(self, results: List[ActionResult]) -> bool:
        return any(getattr(result, "is_done", False) for result in results)

    async def _update_state(
        self,
        browser_state: BrowserStateSummary,
        model_output: AgentOutput,
        results: List[ActionResult],
    ) -> None:
        self.curr_dom_str = browser_state.dom_state.llm_representation(
            include_attributes=INCLUDE_ATTRIBUTES
        )
        self.agent_context.update(
            self.agent_state.step, model_output.action, results, model_output.current_state
        )

        if browser_state.screenshot:
            self._log(
                f"Storing screenshot for step {self.agent_state.step}, screenshot length: {len(browser_state.screenshot)}"
            )
            screenshot_path = await self.screenshot_service.store_screenshot(
                browser_state.screenshot, self.agent_state.step
            )
            self._log(f"Screenshot stored at: {screenshot_path}")
        else:
            self._log(f"No screenshot present for step {self.agent_state.step}")

    def _log(self, msg: str) -> None:
        agent_log.info(msg)
        full_log.info(msg)

    def _handle_error(self, e: Exception) -> None:
        if isinstance(e, LLMNextActionsError):
            self._log(f"LLMNextActionsError: {e.errors}")
        else:
            import traceback
            self._log("Error in step")
            self._log(f"Stack trace: {traceback.format_exc()}")

    def _log_state(self, model_output: AgentOutput, agent_msgs: List[Dict[str, str]]) -> None:
        self._log(
            f"========== SimpleSteppedAgent State: {self.agent_state.curr_step()}/{self.agent_state.max_steps} =========="
        )
        for msg in agent_msgs[:-1]:
            full_log.info(msg["content"])  # system and history
        self._log(agent_msgs[-1]["content"])  # main user prompt
        self._log(f"Step {self.agent_state.step} completed")
