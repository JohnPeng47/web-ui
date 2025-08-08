import json
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Type
from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel

from pydantic import BaseModel
from browser_use.browser.context import BrowserContext
from browser_use.browser.views import BrowserState
from browser_use.controller.service import Controller
from browser_use.agent.views import ActionResult, AgentOutput, ActionModel
from browser_use.agent.prompts import SystemPrompt, AgentMessagePrompt

from json_repair import repair_json

# Your existing light-weight wrappers
from src.llm_models import LLMHub
from .custom_views import CustomAgentOutput
from .custom_message_manager import CustomMessageManager, CustomMessageManagerSettings
from .custom_prompts import CustomAgentMessagePrompt

from pentest_bot.logger import get_agent_loggers

agent_log, full_log = get_agent_loggers()

# Optional: keep HTTP capture hook if you actually use it
try:
    from .http_history import HTTPHistory, HTTPHandler  # noqa
    HAS_HTTP = True
except Exception:
    HAS_HTTP = False

NO_OP_TASK = "Do nothing unless necessary. If a popup appears, dismiss it. Then emit done."

# TODO: find out what the hell this does
INCLUDE_ATTRIBUTES: List[str] = (
    ["title", "type", "name", "role", "aria-label", "placeholder", "value", "alt"]
)


class AgentState(BaseModel):
    curr_url: str

class AgentContext:
    """The main interface for interacting agent step history"""
    def __init__(self, agent_steps: List[Tuple[List[ActionModel], List[ActionResult]]]):
        self._ctxt = agent_steps
        self._curr_step = 0

    # @classmethod
    # def from_db(cls, agent_steps: List["AgentStepORM"]) -> "AgentContext":
    #     return cls([AgentStep.from_db(s) for s in agent_steps])
    
    def update(self, actions: List[ActionModel], results: List[ActionResult]) -> None:
        self._ctxt.append((actions, results))

    def steps(self) -> List[Tuple[List[ActionModel], List[ActionResult]]]:
        return self._ctxt

    def prev_step(self) -> Tuple[List[ActionModel], List[ActionResult]] | Tuple[None, None]:
        if not self._ctxt:
            return None, None
        return self._ctxt[-1]
    
    # def history(self, end: Optional[int] = None) -> str:
    #     return "\n".join([f"[Step {s[0].model_dump_json(exclude_unset=True)}]: {s[1].model_dump_json(exclude_unset=True)}" for s in self._ctxt])

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

        self._step = 0
        self.max_steps = max_steps
        self.agent_context = AgentContext([])
        # TODO: check how url is updated in old code
        self.agent_state = AgentState(curr_url="")

        # TODO: deprecate and replace
        self.sys_prompt = agent_sys_prompt
        self.ActionModel = self.controller.registry.create_action_model()
        self.AgentOutput = CustomAgentOutput.type_with_custom_actions(self.ActionModel)

        # Optional HTTP capture hook
        self.http_handler = None
        self.http_history = None
        if http_capture and HAS_HTTP:
            self.http_handler = HTTPHandler()
            self.http_history = HTTPHistory()
            self.browser_context.req_handler = self.http_handler.handle_request  # type: ignore[attr-defined]
            self.browser_context.res_handler = self.http_handler.handle_response  # type: ignore[attr-defined]

    async def _build_agent_prompt(self) -> List[BaseMessage]:
        _, url, content = await self._get_browser_state()
        agent_prompt = """
Current step: {step_number}/{max_steps}

Task: {task}
Current url: {curr_url}
Interactive Elements: {interactive_elements}
""".format(
    step_number=self._step,
    max_steps=self.max_steps,
    task=self.task, 
    curr_url=url, 
    interactive_elements=content
)
        actions, results = self.agent_context.prev_step()
        if actions and results:
            agent_prompt += "\n **Previous Actions** \n"
            agent_prompt += f'Previous step: {self._step - 1}/{self.max_steps} \n'
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

    async def _get_browser_state(self) -> Tuple[BrowserState, str, str]:
        """
        1) Get browser state (the only state we truly need each turn).
        """
        browser_state = await self.browser_context.get_state()
        page = await self.browser_context.get_current_page()
        url = page.url
        # Keep it simple: the LLM sees only a compact string of clickable elements
        content = browser_state.element_tree.clickable_elements_to_string(include_attributes=INCLUDE_ATTRIBUTES)
        return browser_state, url, content

    async def _llm_next_actions(
        self, input_messages: List[BaseMessage]
    ) -> CustomAgentOutput:
        """
        2) Call the LLM and parse actions.
        """
        ai_msg: BaseMessage = self.llm.get("browser_use").invoke(input_messages)
        # Normalize content to string
        content = ai_msg.content
        if isinstance(content, list):
            # flatten segments into concatenated text parts
            parts: List[str] = []
            for item in content:
                try:
                    if isinstance(item, dict) and "text" in item:
                        parts.append(str(item["text"]))
                    else:
                        parts.append(str(item))
                except Exception:
                    continue
            content = "\n".join(parts)
        if not isinstance(content, str):
            content = json.dumps(content)
        # Strip any fenced JSON and repair if needed
        raw = content.replace("```json", "").replace("```", "")
        payload = json.loads(repair_json(raw))
        parsed: AgentOutput = self.AgentOutput(**payload)
        return parsed  # type: ignore[return-value]

    async def step(self) -> List[ActionResult]:
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

        model_output = await self._llm_next_actions(agent_prompt) # type: ignore
        results = await self._execute_actions(self.browser_context, model_output.action)

        self.agent_context.update(model_output.action, results)
        agent_log.info(f"Step {self._step} completed")

        # Optional: flush HTTP logs here if you wired http_capture
        # if self.http_handler and self.http_history:
        #     http_msgs = await self.http_handler.flush()
        #     filtered = self.http_history.filter_http_messages(http_msgs)
        #     _ = filtered  # do whatever you want with them

        return results

    async def run(self) -> None:
        for _ in range(self.max_steps):
            self._step += 1
            await self.step()
