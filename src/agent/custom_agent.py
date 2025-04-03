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
import platform
from browser_use.agent.prompts import SystemPrompt, AgentMessagePrompt
from browser_use.agent.service import Agent
from browser_use.agent.message_manager.utils import convert_input_messages, extract_json_from_model_output, \
    save_conversation
from browser_use.agent.views import (
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

# Exceptions
from google.api_core.exceptions import ResourceExhausted
from openai import RateLimitError
from pydantic import ValidationError

from johnllm.johnllm import LLMModel

from .state import CurrentState
from .custom_message_manager import CustomMessageManager, CustomMessageManagerSettings
from .custom_views import CustomAgentOutput, CustomAgentStepInfo, CustomAgentState
from .http_handler import HTTPMessage, HTTPRequest, HTTPResponse
from .pentest_prompts import get_pentest_message


import logging
import os

# Configure logging to write to both file and console
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

Context = TypeVar('Context')

DEFAULT_INCLUDE_MIME = ["html", "script", "xml", "flash", "other_text"]
DEFAULT_INCLUDE_STATUS = ["2xx", "3xx", "4xx", "5xx"]
MAX_PAYLOAD_SIZE = 4000
MODEL_NAME = "gpt-4o"

class HTTPHandler:
    def __init__(self):
        self._messages = []
        # track messages at each agent step
        self._step_messages = []
        self._request_queue = []
        
    async def handle_request(self, request: Request):
        http_request = HTTPRequest(request)
        self._request_queue.append(http_request)

    async def handle_response(self, response: Response):
        if not response:
            return
        req_match = HTTPRequest(response.request)
        http_response = HTTPResponse(response)
        matching_request = next(
            (req for req in self._request_queue if req._request == response.request),
            None
        )
        if matching_request:
            self._request_queue.remove(matching_request)

        self._step_messages.append(
            HTTPMessage(request=req_match, response=http_response)
        )

    def flush(self) -> List[HTTPMessage]:
        """Called by agent to flush current messages and reset state"""
        unmatched = [HTTPMessage(request=req, response=None) for req in self._request_queue]

        session_msgs = self._step_messages 
        self._request_queue = []
        self._step_messages = []
        self._messages.extend(unmatched)    
        self._messages.extend(session_msgs)

        return session_msgs

# TODO: consider making this stateful so that we can track messages across steps
def filter_http_messages(messages: List[HTTPMessage], 
                         include_mime_types: List[str] = DEFAULT_INCLUDE_MIME,
                         include_status_codes: List[str] = DEFAULT_INCLUDE_STATUS,
                         max_payload_size: int = 4000) -> List[HTTPMessage]:
    """
    Filter HTTP messages based on specified criteria
    
    Args:
        messages: List of HTTPMessage objects to filter
        include_mime_types: List of MIME types to include (html, script, xml, flash, other_text, css, images, other_binary)
        include_status_codes: List of status code ranges to include (2xx, 3xx, 4xx, 5xx)
        max_payload_size: Maximum payload size in bytes (if None, no limit)
        
    Returns:
        Filtered list of HTTPMessage objects
    """
    # Default values matching the screenshot
    if include_mime_types is None:
        include_mime_types = ["html", "script", "xml", "flash", "other_text"]
    
    if include_status_codes is None:
        include_status_codes = ["2xx", "3xx", "4xx", "5xx"]
    
    # MIME type filters  
    mime_filters = {
        "html": lambda ct: "text/html" in ct,
        "script": lambda ct: "javascript" in ct or "application/json" in ct,
        "xml": lambda ct: "xml" in ct,
        "flash": lambda ct: "application/x-shockwave-flash" in ct,
        "other_text": lambda ct: "text/" in ct and not any(x in ct for x in ["html", "xml", "css"]),
        "css": lambda ct: "text/css" in ct,
        "images": lambda ct: "image/" in ct,
        "other_binary": lambda ct: not any(x in ct for x in ["text/", "image/", "application/json", "application/javascript"])
    }
    
    # Status code filters
    status_filters = {
        "2xx": lambda code: 200 <= code < 300,
        "3xx": lambda code: 300 <= code < 400,
        "4xx": lambda code: 400 <= code < 500,
        "5xx": lambda code: 500 <= code < 600
    }
    
    filtered_messages = []
    
    for msg in messages:
        # Skip messages with no response
        if not msg.response:
            print(f"[FILTER] Excluding {msg.request.url} - No response")
            continue
            
        content_type = msg.response.get_content_type()
        payload_size = msg.response.get_response_size()
        status_code = msg.response.status
        
        # Check MIME type filter
        mime_match = False
        for mime_type in include_mime_types:
            if mime_type in mime_filters and mime_filters[mime_type](content_type):
                mime_match = True
                break
                
        if not mime_match:
            print(f"[FILTER] Excluding {msg.request.url} - MIME type {content_type} not in allowed types")
            continue
            
        # Check status code filter
        status_match = False
        for status_range in include_status_codes:
            if status_range in status_filters and status_filters[status_range](status_code):
                status_match = True
                break
                
        if not status_match:
            print(f"[FILTER] Excluding {msg.request.url} - Status code {status_code} not in allowed ranges")
            continue
            
        # Check payload size filter if specified
        if max_payload_size is not None and payload_size > max_payload_size:
            print(f"[FILTER] Excluding {msg.request.url} - Payload size {payload_size} exceeds max {max_payload_size}")
            continue
            
        filtered_messages.append(msg)
    return filtered_messages

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
    ):
        self.http_handler = HTTPHandler()
        if browser_context:
            browser_context.req_handler = self.http_handler.handle_request
            browser_context.res_handler = self.http_handler.handle_response
        
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

    def _log_response(self, response: CustomAgentOutput) -> None:
        """Log the model's response"""
        if "Success" in response.current_state.evaluation_previous_goal:
            emoji = "✅"
        elif "Failed" in response.current_state.evaluation_previous_goal:
            emoji = "❌"
        else:
            emoji = "🤷"

        logger.info(f"{emoji} Eval: {response.current_state.evaluation_previous_goal}")
        logger.info(f"🧠 New Memory: {response.current_state.important_contents}")
        logger.info(f"🤔 Thought: {response.current_state.thought}")
        logger.info(f"🎯 Next Goal: {response.current_state.next_goal}")
        for i, action in enumerate(response.action):
            logger.info(
                f"🛠️  Action {i + 1}/{len(response.action)}: {action.model_dump_json(exclude_unset=True)}"
            )

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

        logger.info(f"🧠 All Memory: \n{step_info.memory}")

    @time_execution_async("--get_next_action")
    async def get_next_action(self, input_messages: list[BaseMessage]) -> AgentOutput:
        """Get next action from LLM based on current state"""

        ai_message: CurrentState = self.llm.invoke(input_messages, model_name=MODEL_NAME, response_format=CurrentState)
        converted_msg = BaseMessage(content=ai_message.model_dump())
        self.message_manager._add_message_with_tokens(converted_msg)

        # if ai_message.reasoning_content:
        #     logger.info("🤯 Start Deep Thinking: ")
        #     logger.info(ai_message.reasoning_content)
        #     logger.info("🤯 End Deep Thinking")

        parsed: AgentOutput = self.AgentOutput(**ai_message.model_dump())
        if parsed is None:
            logger.debug(ai_message.content)
            raise ValueError('Could not parse response.')

        # cut the number of actions to max_actions_per_step if needed
        if len(parsed.action) > self.settings.max_actions_per_step:
            parsed.action = parsed.action[: self.settings.max_actions_per_step]
        self._log_response(parsed)
        return parsed
    
    async def _run_planner(self) -> Optional[str]:
        """Run the planner to analyze state and suggest next steps"""
        # Skip planning if no planner_llm is set
        if not self.settings.planner_llm:
            return None

        # Create planner message history using full message history
        planner_messages = [
            PlannerPrompt(self.controller.registry.get_prompt_description()).get_system_message(),
            *self.message_manager.get_messages()[1:],  # Use full message history except the first
        ]

        if not self.settings.use_vision_for_planner and self.settings.use_vision:
            last_state_message: HumanMessage = planner_messages[-1]
            # remove image from last state message
            new_msg = ''
            if isinstance(last_state_message.content, list):
                for msg in last_state_message.content:
                    if msg['type'] == 'text':
                        new_msg += msg['text']
                    elif msg['type'] == 'image_url':
                        continue
            else:
                new_msg = last_state_message.content

            planner_messages[-1] = HumanMessage(content=new_msg)

        # Get planner output
        response = await self.settings.planner_llm.ainvoke(planner_messages)
        plan = str(response.content)
        last_state_message = self.message_manager.get_messages()[-1]
        if isinstance(last_state_message, HumanMessage):
            # remove image from last state message
            if isinstance(last_state_message.content, list):
                for msg in last_state_message.content:
                    if msg['type'] == 'text':
                        msg['text'] += f"\nPlanning Agent outputs plans:\n {plan}\n"
            else:
                last_state_message.content += f"\nPlanning Agent outputs plans:\n {plan}\n "

        try:
            plan_json = json.loads(plan.replace("```json", "").replace("```", ""))
            logger.info(f'📋 Plans:\n{json.dumps(plan_json, indent=4)}')

            if hasattr(response, "reasoning_content"):
                logger.info("🤯 Start Planning Deep Thinking: ")
                logger.info(response.reasoning_content)
                logger.info("🤯 End Planning Deep Thinking")

        except json.JSONDecodeError:
            logger.info(f'📋 Plans:\n{plan}')
        except Exception as e:
            logger.debug(f'Error parsing planning analysis: {e}')
            logger.info(f'📋 Plans: {plan}')
        return plan

    @time_execution_async("--step")
    async def step(self, step_info: Optional[CustomAgentStepInfo] = None) -> None:
        """Execute one step of the task"""
        logger.info(f"\n📍 Step {self.state.n_steps}")
        state = None
        model_output = None
        result: list[ActionResult] = []
        step_start_time = time.time() 
        tokens = 0

        try:
            # Agent: 
            # add the response/requests results from executing action to 
            # the agent state
            # TODO: consider adding timeout here to wait for all responses to return
            # TODO: alternatively, we can consider encapsulating res/req in promises, and adding belated pairs to
            # future state
            msgs = self.http_handler.flush()
            filtered_msgs = filter_http_messages(msgs)
            
            state = await self.browser_context.get_state()

            pentest_prompt = await get_pentest_message(state, self.state.last_action, self.state.last_result, step_info, filtered_msgs)
            if pentest_prompt.content[0]:
                pentest_messages = self.llm.invoke([pentest_prompt], model_name=MODEL_NAME)
                pentest_analysis = pentest_messages
            else:
                pentest_analysis = ""
            
            logger.info(f"[Pentest Prompt]: {pentest_prompt.content}")
            logger.info(f"[Pentest Analysis]: {pentest_analysis}")

            await self._raise_if_stopped_or_paused()
            self.message_manager.add_state_message(state, self.state.last_action, self.state.last_result, step_info, pentest_analysis, use_vision=self.settings.use_vision)
            if self.settings.planner_llm and self.state.n_steps % self.settings.planner_interval == 0:
                await self._run_planner()
            input_messages = self.message_manager.get_messages()
            tokens = self._message_manager.state.history.current_tokens

            # logging
            for i, msg in enumerate(input_messages):
                logger.info(f"{i + 1}. [MESSAGE]")
                if isinstance(msg.content, list): 
                    content = ""
                    for item in msg.content:
                        if isinstance(item, dict) and "text" in item:
                            content += item["text"]
                    logger.info(content)
                else:
                    logger.info(msg.content)

            logger.info(f"📨 Input messages: {len(input_messages )}")
            try:
                model_output = await self.get_next_action(input_messages)
                self.update_step_info(model_output, step_info)
                self.state.n_steps += 1

                if self.register_new_step_callback:
                    await self.register_new_step_callback(state, model_output, self.state.n_steps)

                if self.settings.save_conversation_path:
                    target = self.settings.save_conversation_path + f'_{self.state.n_steps}.txt'
                    save_conversation(input_messages, model_output, target,
                                      self.settings.save_conversation_path_encoding)

                if self.model_name != "deepseek-reasoner":
                    # remove prev message
                    self.message_manager._remove_state_message_by_index(-1)
                await self._raise_if_stopped_or_paused()
            except Exception as e:
                # model call failed, remove last state message from history
                self.message_manager._remove_state_message_by_index(-1)
                raise e
 
            result: list[ActionResult] = await self.multi_act(model_output.action)
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
                logger.info(f"📄 Result: {result[-1].extracted_content}")

            self.state.consecutive_failures = 0

        except InterruptedError:
            logger.debug("Agent paused")
            self.state.last_result = [
                ActionResult(
                    error="The agent was paused - now continuing actions might need to be repeated",
                    include_in_memory=True
                )
            ]
            return

        except (ValidationError, ValueError, RateLimitError, ResourceExhausted) as e:
            result = await self._handle_step_error(e)
            self.state.last_result = result

        except Exception as e:
            logger.error(f"Error in step {self.state.n_steps}: {e}")
            logger.error(traceback.format_exc())
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
                    step_error=[r.error for r in result if r.error] if result else ['No result'],
                )
            )
            if not result:
                return

            if state:
                metadata = StepMetadata(
                    step_number=self.state.n_steps,
                    step_start_time=step_start_time,
                    step_end_time=step_end_time,
                    input_tokens=tokens,
                )
                self._make_history_item(model_output, state, result, metadata)

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
                    logger.error(f'❌ Stopping due to {self.settings.max_failures} consecutive failures')
                    break

                # Check control flags before each step
                if self.state.stopped:
                    logger.info('Agent stopped')
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
                logger.info("❌ Failed to complete task in maximum steps")
                if not self.state.extracted_content:
                    self.state.history.history[-1].result[-1].extracted_content = step_info.memory
                else:
                    self.state.history.history[-1].result[-1].extracted_content = self.state.extracted_content

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
