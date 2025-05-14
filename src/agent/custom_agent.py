import json
import logging
import pdb
import traceback
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Type, TypeVar
from PIL import Image, ImageDraw, ImageFont
import os
import base64
import io
import asyncio
import time
from enum import Enum
from pydantic import BaseModel
from browser_use.agent.prompts import SystemPrompt, AgentMessagePrompt
from browser_use.agent.service import Agent
from browser_use.agent.message_manager.utils import convert_input_messages, extract_json_from_model_output, \
    save_conversation
from browser_use.agent.views import (
    ActionModel,
    ActionResult,
    AgentError,
    AgentHistory,
    AgentHistoryList,
    AgentOutput,
    AgentSettings,
    AgentState,
    AgentStepInfo,
    StepMetadata,
    ToolCallingMethod,
)
from browser_use.agent.gif import create_history_gif
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext
from browser_use.browser.views import BrowserStateHistory
from browser_use.controller.service import Controller
from browser_use.telemetry.views import (
    AgentEndTelemetryEvent,
    AgentRunTelemetryEvent,
    AgentStepTelemetryEvent,
)
from browser_use.utils import time_execution_async
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage
)
from browser_use.browser.views import BrowserState, BrowserStateHistory
from browser_use.agent.prompts import PlannerPrompt
from playwright.sync_api import Request, Response
from dataclasses import dataclass

from json_repair import repair_json
from src.utils.agent_state import AgentState
from src.agent.client import AgentClient

from johnllm import LLMModel, LMP
from httplib import HTTPRequest, HTTPResponse, HTTPMessage

# from .state import CustomAgentOutput
from common.agent import BrowserActions
from .custom_views import CustomAgentOutput
from .custom_message_manager import CustomMessageManager, CustomMessageManagerSettings
from .custom_views import CustomAgentStepInfo, CustomAgentState
from .http_history import HTTPHistory, HTTPFilter, DEFAULT_HTTP_FILTER
from .pentest_prompts import get_agent_prompt
from .logger import AgentLogger

import json
import logging
import os

Context = TypeVar('Context')

DEFAULT_INCLUDE_MIME = ["html", "script", "xml", "flash", "other_text"]
DEFAULT_INCLUDE_STATUS = ["2xx", "3xx", "4xx", "5xx"]
MAX_PAYLOAD_SIZE = 4000
DEFAULT_PER_REQUEST_TIMEOUT = 5.0     # seconds to wait for *each* unmatched request
DEFAULT_SETTLE_TIMEOUT      = 1.0     # seconds of network "silence" after the *last* response
POLL_INTERVAL               = 0.05    # how often we poll internal state

MODEL_NAME = "gpt-4.1"

class AgentObservations(str, Enum):
    SITE_STRUCTURE = "site_structure"

class NewPage(BaseModel):
    is_new_page: bool
        
class IsNewPage(LMP):
    prompt = """
You are tasked with determining if the current DOM state of a browser is the same or different page from the previous one,
indicating that the browser has executed a navigational action between the two states. Be careful to differentiate between
different webpages and the same webpage with a slightly changed view (ie. popup, menu dropdown, etc.)

Here is the new page:
{{new_page}}

Here is the previous page:
{{old_page}}

You are tasked with determining if the current DOM state of a browser is the same or different page from the previous one,
indicating that the browser has executed a navigational action between the two states. Be careful to differentiate between
different webpages and the same webpage with a slightly changed view (ie. popup, menu dropdown, etc.)

Now answer, has the page changed?
"""
    response_format = NewPage

class PageObservation(BaseModel):
    observation: str

class MakePageObservation(LMP):
    prompt = """
You are conducting a web browser navigation of a particular application, on this page. 
You are responsible for generating a wiki of the page {{page_url}} and its features and interactions with the backend

Here is the page:
{{page_content}}

Here are your previous observations on this page:
{{page_observations}}

A new action has been taken on this page:
{{browser_action}}

For the executed agent action, decide whether or not to make an observation
Only do so when the *action has exercised some novel functionality* not yet covered under existing observations
Here are some additional rules/styles for writing your observations:
- focus on terse descriptions that involve tying backend http requests/responses to browser actions
- make a note of features that span multiple pages, and describe the partial feature implemented on this page

Now make your observation
"""
    response_format = PageObservation

# TODO: LOGGING QUESTION:
# how to handle logging in functions not defined as part of class
class HTTPHandler:
    def __init__(self):
        self._messages = []
        # track messages at each agent step
        self._step_messages: List[HTTPMessage] = []
        self._request_queue: List[HTTPRequest] = []
        
    async def handle_request(self, request: Request):
        try:
            http_request = HTTPRequest.from_pw(request)
            self._request_queue.append(http_request)
        except Exception as e:
            print("Error handling request: ", e)

    async def handle_response(self, response: Response):
        try:
            if not response:
                return

            req_match = HTTPRequest.from_pw(response.request)
            http_response = HTTPResponse.from_pw(response)
            matching_request = next(
                (req for req in self._request_queue if req.url == response.request.url and req.method == response.request.method),
                None
            )
            if matching_request:
                self._request_queue.remove(matching_request)

            self._step_messages.append(
                HTTPMessage(request=req_match, response=http_response)
            )
        except Exception as e:
            print("Error handling response: ", e)

    async def flush(
        self,
        *,
        per_request_timeout: float = DEFAULT_PER_REQUEST_TIMEOUT,
        settle_timeout: float      = DEFAULT_SETTLE_TIMEOUT,
    ) -> List["HTTPMessage"]:
        """
        Waits until either
          • every outstanding request has been answered **or**
          • `per_request_timeout` elapsed for that request,
        *and* the network has been quiet for `settle_timeout` seconds after the
        very last response captured.

        Returns the list of (request, response) pairs collected *since the last
        flush*, exactly like the old synchronous version.
        """
        loop = asyncio.get_running_loop()

        # ────────────────────────────────────────────────────────────────────
        # Book‑keeping helpers
        # ────────────────────────────────────────────────────────────────────
        # Timestamp when we first saw each unmatched request
        req_start: Dict["HTTPRequest", float] = {
            req: loop.time() for req in self._request_queue
        }

        # Index of the last response we have observed; used for the "quiet"
        # timer.  We *only* reset the quiet timer when a new response arrives.
        last_seen_response_idx = len(self._step_messages)
        last_response_time     = loop.time()              # seed with *now*

        # ────────────────────────────────────────────────────────────────────
        # Main wait‑loop
        # ────────────────────────────────────────────────────────────────────
        while True:
            await asyncio.sleep(POLL_INTERVAL)
            now = loop.time()

            # 1️⃣  Discard requests that have exceeded the per‑request timeout
            for req in list(self._request_queue):
                if now - req_start.get(req, now) >= per_request_timeout:
                    # promote "timed‑out" requests to unmatched messages
                    self._messages.append(HTTPMessage(request=req, response=None))
                    self._request_queue.remove(req)

            # 2️⃣  Check if new responses came in since last iteration
            if len(self._step_messages) != last_seen_response_idx:
                last_seen_response_idx = len(self._step_messages)
                last_response_time     = now          # reset quiet timer

            # 3️⃣  Exit conditions
            queue_empty     = not self._request_queue
            quiet_enough    = (now - last_response_time) >= settle_timeout

            if queue_empty and quiet_enough:
                break

        # ────────────────────────────────────────────────────────────────────
        # Finalize flush – exactly like the original version
        # ────────────────────────────────────────────────────────────────────
        # any *still* unmatched requests → turn them into messages
        unmatched = [
            HTTPMessage(request=req, response=None) for req in self._request_queue
        ]

        session_msgs         = self._step_messages
        self._request_queue  = []
        self._step_messages  = []
        self._messages.extend(unmatched)
        self._messages.extend(session_msgs)

        return session_msgs

class CustomAgent(Agent):
    def __init__(
            self,
            task: str,
            llm: LLMModel,
            add_infos: str = "",
            # Optional parameters
            browser: Browser | None = None,
            browser_context: BrowserContext | None = None,
            controller: Controller[Context] = Controller(),
            # Initial agent run parameters
            sensitive_data: Optional[Dict[str, str]] = None,
            initial_actions: Optional[List[Dict[str, Dict[str, Any]]]] = None,
            # Cloud Callbacks
            register_new_step_callback: Callable[['BrowserState', 'AgentOutput', int], Awaitable[None]] | None = None,
            register_done_callback: Callable[['AgentHistoryList'], Awaitable[None]] | None = None,
            register_external_agent_status_raise_error_callback: Callable[[], Awaitable[bool]] | None = None,
            # Agent settings
            use_vision: bool = True,
            use_vision_for_planner: bool = False,
            save_conversation_path: Optional[str] = None,
            save_conversation_path_encoding: Optional[str] = 'utf-8',
            max_failures: int = 3,
            retry_delay: int = 10,
            system_prompt_class: Type[SystemPrompt] = SystemPrompt,
            agent_prompt_class: Type[AgentMessagePrompt] = AgentMessagePrompt,
            max_input_tokens: int = 128000,
            validate_output: bool = False,
            message_context: Optional[str] = None,
            generate_gif: bool | str = False,
            available_file_paths: Optional[list[str]] = None,
            include_attributes: list[str] = [
                'title',
                'type',
                'name',
                'role',
                'aria-label',
                'placeholder',
                'value',
                'alt',
                'aria-expanded',
                'data-date-format',
            ],
            max_actions_per_step: int = 10,
            tool_calling_method: Optional[ToolCallingMethod] = 'auto',
            page_extraction_llm: Optional[BaseChatModel] = None,
            planner_llm: Optional[BaseChatModel] = None,
            planner_interval: int = 1,  # Run planner every N steps
            # Inject state
            injected_agent_state: Optional[AgentState] = None,
            context: Context | None = None,
            history_file: Optional[str] = None,
            agent_client: Optional[AgentClient] = None,
            app_id: Optional[str] = None
    ):        
        super(CustomAgent, self).__init__(
            task=task,
            llm=llm,
            browser=browser,
            browser_context=browser_context,
            controller=controller,
            sensitive_data=sensitive_data,
            initial_actions=initial_actions,
            register_new_step_callback=register_new_step_callback,
            register_done_callback=register_done_callback,
            register_external_agent_status_raise_error_callback=register_external_agent_status_raise_error_callback,
            use_vision=use_vision,
            use_vision_for_planner=use_vision_for_planner,
            save_conversation_path=save_conversation_path,
            save_conversation_path_encoding=save_conversation_path_encoding,
            max_failures=max_failures,
            retry_delay=retry_delay,
            system_prompt_class=system_prompt_class,
            max_input_tokens=max_input_tokens,
            validate_output=validate_output,
            message_context=message_context,
            generate_gif=generate_gif,
            available_file_paths=available_file_paths,
            include_attributes=include_attributes,
            max_actions_per_step=max_actions_per_step,
            tool_calling_method=tool_calling_method,
            page_extraction_llm=page_extraction_llm,
            planner_llm=planner_llm,
            planner_interval=planner_interval,
            injected_agent_state=injected_agent_state,
            context=context,
        )
        self.curr_page = None
        self.history_file = history_file
        self.http_handler = HTTPHandler()
        self.http_history = HTTPHistory(
            http_filter=DEFAULT_HTTP_FILTER
        )
        self.agent_client = agent_client
        self.agent_client.set_shutdown(self.shutdown)

        self.app_id = app_id
        self.agent_id = None
        if agent_client and not app_id:
            raise ValueError("app_id must be provided when agent_client is set")
        
        self.page_observations = {}
        
        # TODO: probably not a good idea to use none global logging solution
        self.log = AgentLogger(name=self.agent_client.username)
        self.observations = {title.value: "" for title in AgentObservations}
        if browser_context:
            # logger.info("Registering HTTP handlers")
            browser_context.req_handler = self.http_handler.handle_request
            browser_context.res_handler = self.http_handler.handle_response
            browser_context.page_handler = self.handle_page

        # STEP STATE VARIABLES:
        # put variables that need to hold state between  step() here
        self.cross_step_prev_page_str: Optional[str] = None
        self.cross_step_prev_url: Optional[str] = None

        self.state = injected_agent_state or CustomAgentState()
        self.add_infos = add_infos
        self._message_manager = CustomMessageManager(
            task=task,
            system_message=self.settings.system_prompt_class(
                self.available_actions,
                max_actions_per_step=self.settings.max_actions_per_step,
            ).get_system_message(),
             settings=CustomMessageManagerSettings(
                max_input_tokens=self.settings.max_input_tokens,
                include_attributes=self.settings.include_attributes,
                message_context=self.settings.message_context,
                sensitive_data=sensitive_data,
                available_file_paths=self.settings.available_file_paths,
                agent_prompt_class=agent_prompt_class
            ),
            state=self.state.message_manager_state,
        )
        
    def handle_page(self, page):
        self.log.context.info(f"[PLAYWRIGHT] >>>>>>>>>>>")
        self.log.context.info(f"[PLAYWRIGHT] Frame {page}")
        self.curr_page = page

    def _is_new_page(self, old_page: str, new_page: str) -> bool:
        """Check if the new page is different from the old page"""
        try:
            is_new_page = IsNewPage().invoke(
                model=self.llm,
                model_name=MODEL_NAME,
                prompt_args={
                    "new_page": new_page,
                    "old_page": old_page,
                }
            )
            return is_new_page.is_new_page
        except Exception as e:
            self.log.context.error(f"Error in _is_new_page: {e}")
            return False
        
    def _log_response(self, 
                      http_msgs: List[HTTPMessage],
                      current_msg: BaseMessage,
                      response: CustomAgentOutput) -> None:
        """Log the model's response"""
        if "Success" in response.current_state.evaluation_previous_goal:
            emoji = "✅"
        elif "Failed" in response.current_state.evaluation_previous_goal:
            emoji = "❌"
        else:
            emoji = "🤷"

        self.log.action.info(f"{emoji} Eval: {response.current_state.evaluation_previous_goal}")
        self.log.action.info(f"🧠 New Memory: {response.current_state.important_contents}")
        self.log.action.info(f"🤔 Thought: {response.current_state.thought}")
        self.log.action.info(f"🎯 Next Goal: {response.current_state.next_goal}")
        for i, action in enumerate(response.action):
            self.log.action.info(
                f"🛠️  Action {i + 1}/{len(response.action)}: {action.model_dump_json(exclude_unset=True)}"
            )
        self.log.context.info(f"[Prev Messages]: {current_msg.content}")
        self.log.context.info(f"Captured {len(http_msgs)} HTTP Messages")
        for msg in http_msgs:
            self.log.context.info(f"[Agent] {msg.request.url}")

    def _setup_action_models(self) -> None:
        """Setup dynamic action models from controller's registry"""
        # Get the dynamic action model from controller's registry
        self.ActionModel = self.controller.registry.create_action_model()
        # Create output model with the dynamic actions
        self.AgentOutput = CustomAgentOutput.type_with_custom_actions(self.ActionModel)

    def update_step_info(
        self, model_output: CustomAgentOutput, step_info: CustomAgentStepInfo = None
    ):
        """
        update step info
        """
        if step_info is None:
            return

        step_info.step_number += 1
        important_contents = model_output.current_state.important_contents
        if (
                important_contents
                and "None" not in important_contents
                and important_contents not in step_info.memory
        ):
            step_info.memory += important_contents + "\n"

        self.log.action.info(f"🧠 All Memory: \n{step_info.memory}")

    @time_execution_async("--get_next_action")
    async def get_next_action(self, input_messages: list[BaseMessage]) -> AgentOutput:
        """Get next action from LLM based on current state"""

        ai_message: str = self.llm.invoke(
            input_messages, 
            model_name=MODEL_NAME, 
            response_format=None
        )
        converted_msg = BaseMessage(
            content=ai_message,
            type="user"
        )
        self.message_manager._add_message_with_tokens(converted_msg)

        # if ai_message.reasoning_content:
        #     self.log.context.info("🤯 Start Deep Thinking: ")
        #     self.log.context.info(ai_message.reasoning_content)
        #     self.log.context.info("🤯 End Deep Thinking")

        ai_content = ai_message.replace("```json", "").replace("```", "")
        ai_content = repair_json(ai_content)
        parsed_json = json.loads(ai_content)
        parsed: AgentOutput = self.AgentOutput(**parsed_json)

        if parsed is None:
            self.log.context.debug(ai_message.content)
            raise ValueError('Could not parse response.')

        # cut the number of actions to max_actions_per_step if needed
        if len(parsed.action) > self.settings.max_actions_per_step:
            parsed.action = parsed.action[: self.settings.max_actions_per_step]
        return parsed
    
    async def _update_server(self, 
                             http_msgs: List[HTTPMessage], 
                             browser_actions: BrowserActions) -> None:
        """Executed after the agent takes action and browser state is updated"""
        if self.agent_client:
            if not self.agent_id:
                agent_info = await self.agent_client.register_agent(self.app_id)
                self.agent_id = agent_info["id"]

            await self.agent_client.update_server_state(
                self.app_id, 
                self.agent_id, 
                [
                    await msg.to_json() for msg in http_msgs
                ],
                browser_actions
            )

    def _update_state(self, result, model_output, step_info):
        """Update agent state with results from actions"""
       
        # random state update stuff ...
        for ret_ in result:
            if ret_.extracted_content and "Extracted page" in ret_.extracted_content:
                # record every extracted page
                if ret_.extracted_content[:100] not in self.state.extracted_content:
                    self.state.extracted_content += ret_.extracted_content

        self.state.last_result = result
        self.state.last_action = model_output.action
        if len(result) > 0 and result[-1].is_done:
            if not self.state.extracted_content:
                self.state.extracted_content = step_info.memory
            result[-1].extracted_content = self.state.extracted_content
            self.log.action.info(f"📄 Result: {result[-1].extracted_content}")

        self.state.consecutive_failures = 0

    @time_execution_async("--step")
    async def step(self, step_info: Optional[CustomAgentStepInfo] = None) -> None:
        """Execute one step of the task"""
        self.log.action.info(f"Step {self.state.n_steps}")
        state_before_actions = None
        model_output = None
        result: list[ActionResult] = []
        step_start_time = time.time()
        tokens = 0
        browser_actions = None

        try:
            state_before_actions = await self.browser_context.get_state()
            url_before_action = (await self.browser_context.get_current_page()).url
            page_str_before_action = state_before_actions.element_tree.clickable_elements_to_string()
            browser_actions = BrowserActions()

            await self._raise_if_stopped_or_paused()
            self.message_manager.add_state_message(
                state_before_actions, 
                self.state.last_action, 
                self.state.last_result, 
                step_info, 
                "", # TODO: pentest prompt, consider removing this
                use_vision=self.settings.use_vision
            )
            input_messages = self.message_manager.get_messages()
            tokens = self._message_manager.state.history.current_tokens
            try:
                # HACK
                for msg in input_messages:
                    msg.type = ""
                model_output = await self.get_next_action(input_messages)                
                self.update_step_info(model_output, step_info)
                self.state.n_steps += 1
                await self._raise_if_stopped_or_paused()

            except Exception as e:
                # model call failed, remove last state message from history
                self.message_manager._remove_state_message_by_index(-1)
                raise e
 
            result: list[ActionResult] = await self.multi_act(model_output.action)

            # NOTE: here we execute analysis on the browser state after executing actions
            state_after_actions = await self.browser_context.get_state() # Ensure fresh state
            page_str_after_actions = state_after_actions.element_tree.clickable_elements_to_string()
            url_after_actions = (await self.browser_context.get_current_page()).url

            is_new_page = self._is_new_page(
                old_page=self.cross_step_prev_page_str if self.cross_step_prev_page_str is not None else page_str_before_action,
                new_page=page_str_after_actions
            )

            self.log.context.info(f"Curr_url:{url_after_actions}, prev_url: {self.cross_step_prev_url or url_before_action}, is_new_page: {is_new_page}")

            # Update instance variables to carry state to the next step
            self.cross_step_prev_url = url_after_actions
            self.cross_step_prev_page_str = page_str_after_actions

            http_msgs = await self.http_handler.flush()
            filtered_msgs = self.http_history.filter_http_messages(http_msgs)
            browser_actions = BrowserActions(
                actions=model_output.action,
                thought=model_output.current_state.thought,
                goal=model_output.current_state.next_goal, 
            )
            
            if self.agent_client:
                await self._update_server(filtered_msgs, browser_actions)

            # update page observations
            obs = MakePageObservation().invoke(
                model=self.llm,
                model_name=MODEL_NAME,
                prompt_args={
                    "page_content": page_str_after_actions,
                    "page_url": url_after_actions,
                    "page_observations": self.page_observations.get(url_after_actions, "[no current on page]"),
                    "browser_action": str(browser_actions)
                }
            )
            self.page_observations[url_after_actions] = obs.observation
            
            self._update_state(result, model_output, step_info)
            self._log_response(
                filtered_msgs,
                current_msg=input_messages[-1],
                response=model_output
            )

        except InterruptedError:
            self.log.context.debug("Agent paused")
            self.state.last_result = [
                ActionResult(
                    error="The agent was paused - now continuing actions might need to be repeated",
                    include_in_memory=True
                )
            ]
            return

        except Exception as e:
            self.log.context.error(f"Error in step {self.state.n_steps}: {e}")
            self.log.context.error(traceback.format_exc())
            step_info.step_number = step_info.max_steps

            raise e

        finally:
            step_end_time = time.time()
            actions = [a.model_dump(exclude_unset=True) for a in model_output.action] if model_output else []
            self.telemetry.capture(
                AgentStepTelemetryEvent(
                    agent_id=self.state.agent_id,
                    step=self.state.n_steps,
                    actions=actions,
                    consecutive_failures=self.state.consecutive_failures,
                    step_error=[r.error for r in result if r.error] if result else ["No result"],
                )
            )
            if not result:
                return

            if state_before_actions: # Use state_before_actions for history item, as it's what LLM saw
                metadata = StepMetadata(
                    step_number=self.state.n_steps,
                    step_start_time=step_start_time,
                    step_end_time=step_end_time,
                    input_tokens=tokens,
                )
                json_msgs = [await msg.to_json() for msg in filtered_msgs]
                self._make_history_item(model_output, state_before_actions, result, json_msgs, metadata=metadata)
            
            for page, obs in self.page_observations.items():
                print("Page observations for page:", page)
                print(obs)


    async def run(self, max_steps: int = 100) -> AgentHistoryList:
        """Execute the task with maximum number of steps"""
        try:
            self._log_agent_run()

            # Execute initial actions if provided
            if self.initial_actions:
                result = await self.multi_act(self.initial_actions, check_for_new_elements=False)
                self.state.last_result = result

            step_info = CustomAgentStepInfo(
                task=self.task,
                add_infos=self.add_infos,
                step_number=1,
                max_steps=max_steps,
                memory="",
            )

            for step in range(max_steps):
                # Check if we should stop due to too many failures
                if self.state.consecutive_failures >= self.settings.max_failures:
                    self.log.context.error(f'❌ Stopping due to {self.settings.max_failures} consecutive failures')
                    break

                # Check control flags before each step
                if self.state.stopped:
                    self.log.context.info('Agent stopped')
                    break

                while self.state.paused:
                    await asyncio.sleep(0.2)  # Small delay to prevent CPU spinning
                    if self.state.stopped:  # Allow stopping while paused
                        break

                await self.step(step_info)

                if self.state.history.is_done():
                    if self.settings.validate_output and step < max_steps - 1:
                        if not await self._validate_output():
                            continue

                    await self.log_completion()
                    break
            else:
                self.log.context.info("❌ Failed to complete task in maximum steps")
                if not self.state.extracted_content:
                    self.state.history.history[-1].result[-1].extracted_content = step_info.memory
                else:
                    self.state.history.history[-1].result[-1].extracted_content = self.state.extracted_content

            if self.history_file:
                self.state.history.save_to_file(self.history_file)

            return self.state.history

        finally:
            self.telemetry.capture(
                AgentEndTelemetryEvent(
                    agent_id=self.state.agent_id,
                    is_done=self.state.history.is_done(),
                    success=self.state.history.is_successful(),
                    steps=self.state.n_steps,
                    max_steps_reached=self.state.n_steps >= max_steps,
                    errors=self.state.history.errors(),
                    total_input_tokens=self.state.history.total_input_tokens(),
                    total_duration_seconds=self.state.history.total_duration_seconds(),
                )
            )

            if not self.injected_browser_context:
                await self.browser_context.close()

            if not self.injected_browser and self.browser:
                await self.browser.close()

            if self.settings.generate_gif:
                output_path: str = 'agent_history.gif'
                if isinstance(self.settings.generate_gif, str):
                    output_path = self.settings.generate_gif

                create_history_gif(task=self.task, history=self.state.history, output_path=output_path)

    async def shutdown(self, reason: str = "Premature shutdown requested") -> None:
        """Shuts down the agent prematurely and performs cleanup."""
        # Check if already stopped to prevent duplicate shutdown calls
        if hasattr(self.state, 'stopped') and self.state.stopped:
            self.log.context.warning("Shutdown already in progress or completed.")
            return

        self.log.context.info(f"Initiating premature shutdown: {reason}")
        # Ensure state has 'stopped' attribute before setting
        if hasattr(self.state, 'stopped'):
             self.state.stopped = True
        else:
             # If AgentState doesn't have stopped, we might need another way
             # to signal termination or handle this case.
             self.log.context.warning("Agent state does not have 'stopped' attribute. Cannot signal stop.")


        # Perform cleanup similar to the finally block in run()
        try:
            # Capture Telemetry for Shutdown Event
            # Check existence of attributes before accessing due to potential type issues
            agent_id = getattr(self.state, 'agent_id', 'unknown_id')
            steps = getattr(self.state, 'n_steps', 0)
            history = getattr(self.state, 'history', None)
            errors = (history.errors() if history else []) + [f"Shutdown: {reason}"]
            input_tokens = history.total_input_tokens() if history else 0
            duration_seconds = history.total_duration_seconds() if history else 0.0

            self.telemetry.capture(
                AgentEndTelemetryEvent(
                    agent_id=agent_id,
                    is_done=False, # Task was not completed normally
                    success=False, # Assume failure on shutdown
                    steps=steps,
                    max_steps_reached=False,
                    errors=errors,
                    total_input_tokens=input_tokens,
                    total_duration_seconds=duration_seconds,
                )
            )

            # Save History
            if self.history_file and history:
                try:
                    history.save_to_file(self.history_file)
                    self.log.context.info(f"Saved agent history to {self.history_file} during shutdown.")
                except Exception as e:
                    self.log.context.error(f"Failed to save history during shutdown: {e}")

            # Close Browser Context
            if not self.injected_browser_context and self.browser_context:
                try:
                    await self.browser_context.close()
                    self.log.context.info("Closed browser context during shutdown.")
                except Exception as e:
                    self.log.context.error(f"Error closing browser context during shutdown: {e}")

            # Close Browser
            if not self.injected_browser and self.browser:
                try:
                    await self.browser.close()
                    self.log.context.info("Closed browser during shutdown.")
                except Exception as e:
                    self.log.context.error(f"Error closing browser during shutdown: {e}")

            # Generate GIF
            if self.settings.generate_gif and history:
                try:
                    output_path: str = 'agent_history_shutdown.gif' # Default name
                    if isinstance(self.settings.generate_gif, str):
                        # Create a shutdown-specific name based on config
                        base, ext = os.path.splitext(self.settings.generate_gif)
                        output_path = f"{base}_shutdown{ext}"

                    self.log.context.info(f"Generating shutdown GIF at {output_path}")
                    create_history_gif(task=f"{self.task} (Shutdown)", history=history, output_path=output_path)
                except Exception as e:
                     self.log.context.error(f"Failed to generate GIF during shutdown: {e}")

        except Exception as e:
            # Catch errors during the shutdown cleanup process itself
            self.log.context.error(f"Error during agent shutdown cleanup: {e}")
            self.log.context.error(traceback.format_exc())
        finally:
             self.log.context.info("Agent shutdown process complete.")
