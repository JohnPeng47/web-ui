import json
from typing import Any, List, Optional, Tuple
from langchain_core.messages import BaseMessage

from pydantic import BaseModel, ValidationError, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from browser_use.browser.context import BrowserContext
from browser_use.browser.views import BrowserState
from browser_use.controller.service import Controller
from browser_use.agent.views import ActionResult, AgentOutput, ActionModel

from common.utils import extract_json
from src.llm_models import LLMHub
from src.agent.custom_views import CustomAgentOutput

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

NO_OP_TASK = "Do nothing unless necessary. If a popup appears, dismiss it. Then emit done."

# TODO: find out what the hell this does
INCLUDE_ATTRIBUTES: List[str] = (
    ["title", "type", "name", "role", "aria-label", "placeholder", "value", "alt"]
)

# TODO List:
# - terminate on success
# - add results from previous steps
# - find way to get the current url
class AgentState(BaseModel):
    step: int
    max_steps: int
    is_done: bool = False

    def curr_step(self) -> int:
        """Always print 1-indexed"""
        return self.step + 1

# Wrapper classes for action and result to introduce a layer of indirection
# for when we potentially want to switch to stagehand
class AgentAction:
    def __init__(self, action: ActionModel):
        self._action = action

    def __str__(self) -> str:
        return self._action.model_dump_json(exclude_unset=True)

class AgentResult:
    def __init__(self, result: ActionResult):
        self._result = result

    def __str__(self) -> str:
        return self._result.model_dump_json(exclude_unset=True)

class AgentStep(BaseModel):
    actions: List[AgentAction]
    results: List[AgentResult]

class AgentContext:
    """The main interface for interacting agent step history"""
    def __init__(self, agent_steps: List[AgentStep]):
        self._ctxt = agent_steps

    def update(self, curr_actions: List[ActionModel], last_results: List[ActionResult]) -> None:
        curr_step = AgentStep(actions=curr_actions, results=last_results)
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

    def history(self, end_step: Optional[int] = None) -> str:
        lines: List[str] = []
        for step in self._ctxt[:end_step]:
            action_json = ", ".join(a.model_dump_json(exclude_unset=True) for a in step.actions)
            result_json = ", ".join(r.model_dump_json(exclude_unset=True) for r in step.results)
            lines.append(f"[Actions: {action_json}] -> [Results: {result_json}]")
        return "\n".join(lines)

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
        max_input_tokens: int = 128000,
        available_file_paths: Optional[List[str]] = None,
        http_capture: bool = False,
    ):
        self.task = start_task or NO_OP_TASK
        self.llm = llm
        self.browser_context = browser_context
        self.controller = controller

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

    async def _build_agent_prompt(self) -> List[dict[str, str]]:
        _, url, content = await self._get_browser_state()
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
        actions, results = self.agent_context.prev_step()
        if actions and results:
            agent_prompt += "\n **Previous Actions** \n"
            agent_prompt += f'Previous step: {self.agent_state.curr_step() - 1}/{self.agent_state.max_steps} \n'
            for i, result in enumerate(results):
                action = actions[i]
                agent_prompt += f"Previous action {i + 1}/{len(results)}: {action.model_dump_json(exclude_unset=True)}\n"
                if result.error:
                    # only use last 300 characters of error
                    error = result.error.split('\n')[-1]
                    agent_prompt += (
                        f"Error of previous action {i + 1}/{len(results)}: ...{error}\n"
                    )
                if result.include_in_memory:
                    if result.extracted_content:
                        agent_prompt += f"Result of previous action {i + 1}/{len(results)}: {result.extracted_content}\n"

        sys_msg = {
            "role": "system",
            "content": self.sys_prompt
        }
        agent_msg = {
            "role": "user",
            "content": agent_prompt
        }
        history = {
            "role": "user",
            "content": self.agent_context.history(self.agent_state.step)
        }
        return [sys_msg, agent_msg]


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

    def _update_state(self, actions: List[ActionModel], results: List[ActionResult]) -> None:
        self.agent_context.update(actions, results)
        self.agent_state.step += 1
        self.agent_state.is_done = self._check_done(results)

    async def step(self):
        """
        One iteration:
          - read browser
          - build messages
          - query LLM
          - execute actions
        """
        # Build prompt for this turn
        agent_prompt = await self._build_agent_prompt()
        agent_log.info(agent_prompt[1]["content"])

        model_output = await self._llm_next_actions(agent_prompt)
        results = await self._execute_actions(self.browser_context, model_output.action)

        self._update_state(model_output.action, results)
        agent_log.info(f"Step {self.agent_state.step} completed")
        
        # Optional: flush HTTP logs here if you wired http_capture
        # if self.http_handler and self.http_history:
        #     http_msgs = await self.http_handler.flush()
        #     filtered = self.http_history.filter_http_messages(http_msgs)
        #     _ = filtered  # do whatever you want with them

    async def run(self) -> None:
        while self.agent_state.step < self.agent_state.max_steps:
            await self.step()
            if self.agent_state.is_done:
                agent_log.info(f"Agent completed successfully @ {self.agent_state.step}/{self.agent_state.max_steps} steps!")
                break