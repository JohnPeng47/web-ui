import json
import traceback
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Type, TypeVar, Set, Deque
import os
import asyncio
import time
from enum import Enum, auto
from pydantic import BaseModel
from collections import deque, defaultdict
from browser_use.agent.prompts import SystemPrompt, AgentMessagePrompt
from browser_use.agent.service import Agent
from browser_use.agent.views import (
	ActionResult,
	AgentHistoryList,
	AgentOutput,
	AgentState,
	StepMetadata,
	ToolCallingMethod,
)
from browser_use.agent.gif import create_history_gif
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext
from browser_use.controller.service import Controller
from browser_use.telemetry.views import (
	AgentEndTelemetryEvent,
	AgentStepTelemetryEvent,
)
from browser_use.utils import time_execution_async
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from browser_use.browser.views import BrowserState
from playwright.sync_api import Request, Response

from json_repair import repair_json
from src.utils.agent_state import AgentState
from src.agent.client import AgentClient

from johnllm import LLMModel, LMP
from httplib import HTTPRequest, HTTPResponse, HTTPMessage

from playwright._impl._errors import TargetClosedError
from logging import getLogger
from logger import init_root_logger

# from .state import CustomAgentOutput
from common.agent import BrowserActions
from .custom_views import CustomAgentOutput
from .custom_message_manager import CustomMessageManager, CustomMessageManagerSettings
from .custom_views import CustomAgentStepInfo, CustomAgentState
from .http_history import HTTPHistory, BAN_LIST
from .logger import AgentLogger

from .discovery import (
	CreatePlan,
	TASK_PROMPT_WITH_PLAN
)

logger = getLogger(__name__)

Context = TypeVar('Context')

DEFAULT_INCLUDE_MIME = ["html", "script", "xml", "flash", "other_text"]
DEFAULT_INCLUDE_STATUS = ["2xx", "3xx", "4xx", "5xx"]
MAX_PAYLOAD_SIZE = 4000
DEFAULT_FLUSH_TIMEOUT       = 5.0    # seconds to wait for all requests to be flushed
DEFAULT_PER_REQUEST_TIMEOUT = 2.0     # seconds to wait for *each* unmatched request
DEFAULT_SETTLE_TIMEOUT      = 1.0     # seconds of network “silence” after the *last* response
POLL_INTERVAL               = 0.5    # how often we poll internal state

MODEL_NAME = "gpt-4.1"

class AgentMode(Enum):
	NAVIGATION = auto()
	TASK_EXECUTION = auto()
	NOOP = auto()

class Event(Enum):
	NAV_SUCCESS    = auto()
	NAV_FAILED     = auto()
	TASK_COMPLETE  = auto()
	BACKTRACK      = auto()
	SHUTDOWN       = auto()

TRANSITIONS = {
	(AgentMode.NAVIGATION, Event.NAV_SUCCESS):    AgentMode.TASK_EXECUTION,
	(AgentMode.NAVIGATION, Event.NAV_FAILED):     AgentMode.NAVIGATION,
	(AgentMode.TASK_EXECUTION, Event.TASK_COMPLETE): AgentMode.NAVIGATION,
	(AgentMode.TASK_EXECUTION, Event.BACKTRACK):  AgentMode.NAVIGATION,
}



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

# TODO: LOGGING QUESTION:
# TODO: really need to simplify logic here
# how to handle logging in functions not defined as part of class
class HTTPHandler:
	def __init__(
		self,
		*,
		banlist: List[str] | None = None,
	):
		self._messages: List[HTTPMessage]      = []
		self._step_messages: List[HTTPMessage] = []
		self._request_queue: List[HTTPRequest] = []
		self._req_start: Dict[HTTPRequest, float] = {}

		# URL filter  ───────────────────────────────────────────────────────
		# A simple substring-based ban list imported from a shared module.
		self._ban_substrings: List[str] = banlist or BAN_LIST
		self._ban_list: Set[str]        = set()   # concrete URLs flagged at run-time

	# ─────────────────────────────────────────────────────────────────────
	# Helper
	# ─────────────────────────────────────────────────────────────────────
	def _is_banned(self, url: str) -> bool:
		"""Return True if the URL matches any ban-substring or was added at runtime."""
		if url in self._ban_list:
			return True
		for s in self._ban_substrings:
			if s in url:
				self._ban_list.add(url)      # cache for fast positive lookup next time
				return True
		return False

	# ─────────────────────────────────────────────────────────────────────
	# Browser-callback handlers
	# ─────────────────────────────────────────────────────────────────────
	async def handle_request(self, request: Request):
		try:
			http_request = HTTPRequest.from_pw(request)
			url          = http_request.url

			if self._is_banned(url):
				logger.debug(f"Dropped banned URL: {url}")
				return

			self._request_queue.append(http_request)
			self._req_start[http_request] = asyncio.get_running_loop().time()
		except Exception as e:
			logger.exception("Error handling request: %s", e)

	async def handle_response(self, response: Response):
		try:
			if not response:
				return

			req_match      = HTTPRequest.from_pw(response.request)
			http_response  = HTTPResponse.from_pw(response)

			matching_request = next(
				(req for req in self._request_queue
				 if req.url == response.request.url and req.method == response.request.method),
				None
			)
			if matching_request:
				self._request_queue.remove(matching_request)
				self._req_start.pop(matching_request, None)

			self._step_messages.append(
				HTTPMessage(request=req_match, response=http_response)
			)
		except Exception as e:
			logger.exception("Error handling response: %s", e)

	# ─────────────────────────────────────────────────────────────────────
	# Flush logic with hard timeout
	# ─────────────────────────────────────────────────────────────────────
	async def flush(
		self,
		*,
		per_request_timeout: float = DEFAULT_PER_REQUEST_TIMEOUT,
		settle_timeout:      float = DEFAULT_SETTLE_TIMEOUT,
		flush_timeout:       float = DEFAULT_FLUSH_TIMEOUT,
	) -> List["HTTPMessage"]:
		"""
		Block until either:
		  • all outstanding requests are answered / timed out and the network
			has been quiet for `settle_timeout` seconds, **or**
		  • `flush_timeout` seconds have elapsed in total.
		"""
		logger.info("Starting HTTP flush")
		loop        = asyncio.get_running_loop()
		start_time  = loop.time()

		last_seen_response_idx = len(self._step_messages)
		last_response_time     = start_time

		while True:
			await asyncio.sleep(POLL_INTERVAL)
			now = loop.time()

			# 0️⃣  Hard timeout check
			if now - start_time >= flush_timeout:
				logger.warning(
					"Flush hit hard timeout of %.1f s; returning immediately", flush_timeout
				)
				break

			# 1️⃣  Per-request time-outs
			for req in list(self._request_queue):
				started_at = self._req_start.get(req, now)
				if now - started_at >= per_request_timeout:
					logger.info("Request timed out: %s", req.url)
					self._messages.append(HTTPMessage(request=req, response=None))
					self._request_queue.remove(req)
					self._req_start.pop(req, None)
				else:
					logger.debug("[REQUEST STAY] %s stay: %.2f s", req.url, now - started_at)

			# 2️⃣  Quiet-period tracking
			if len(self._step_messages) != last_seen_response_idx:
				last_seen_response_idx = len(self._step_messages)
				last_response_time     = now

			# 3️⃣  Exit conditions
			queue_empty  = not self._request_queue
			quiet_enough = (now - last_response_time) >= settle_timeout
			if queue_empty and quiet_enough:
				logger.info("Flush complete")
				break

		# ────────────────────────────────────────────────────────────────
		# Finalise
		# ────────────────────────────────────────────────────────────────
		unmatched = [
			HTTPMessage(request=req, response=None) for req in self._request_queue
		]
		self._req_start.clear()

		session_msgs        = self._step_messages
		self._request_queue = []
		self._step_messages = []
		self._messages.extend(unmatched)
		self._messages.extend(session_msgs)

		logger.info("Returning %d messages from flush", len(session_msgs))
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
			controller: Controller[Context] | None = None,
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
			app_id: Optional[str] = None,
			close_browser: bool = False,
			agent_name: str = ""
	):
		super(CustomAgent, self).__init__(
			task=task,
			llm=llm,
			browser=browser,
			browser_context=browser_context,
			controller=controller or Controller(),
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
			injected_agent_state=None,
			context=context,
		)
		self.llm: LLMModel
		self.agent_name = agent_name
		self.close_browser = close_browser
		self.curr_page = None
		self.history_file = history_file
		self.http_handler = HTTPHandler()
		self.http_history = HTTPHistory()
		self.agent_client = agent_client
		if self.agent_client:
			self.agent_client.set_shutdown(self.shutdown)

		self.app_id = app_id
		self.agent_id = None
		if agent_client and not app_id:
			raise ValueError("app_id must be provided when agent_client is set")
		
		# username = self.agent_client.username if self.agent_client else "default"
		username = self.agent_name if self.agent_name else "default"
		
		# TODO: probably not a good idea to use none global logging solution
		init_root_logger(username)
		self.observations = {title.value: "" for title in AgentObservations}

		if browser_context:
			logger.info("Registering HTTP handlers")
			browser_context.req_handler = self.http_handler.handle_request
			browser_context.res_handler = self.http_handler.handle_response
			# browser_context.page_handler = self.handle_page

		self.state = CustomAgentState()
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

		# State variables used for step()
		self.step_http_msgs = []

	def handle_page(self, page):
		logger.info(f"[PLAYWRIGHT] >>>>>>>>>>>")
		logger.info(f"[PLAYWRIGHT] Frame {page}")
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
			logger.error(f"Error in _is_new_page: {e}")
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

		logger.info(f"{emoji} Eval: {response.current_state.evaluation_previous_goal}")
		logger.info(f"🧠 New Memory: {response.current_state.important_contents}")
		logger.info(f"🤔 Thought: {response.current_state.thought}")
		logger.info(f"🎯 Next Goal: {response.current_state.next_goal}")
		for i, action in enumerate(response.action):
			logger.info(
				f"🛠️  Action {i + 1}/{len(response.action)}: {action.model_dump_json(exclude_unset=True)}"
			)
		logger.info(f"[Prev Messages]: {current_msg.content}")
		logger.info(f"Captured {len(http_msgs)} HTTP Messages")
		for msg in http_msgs:
			logger.info(f"[Agent] {msg.request.url}")

	def _setup_action_models(self) -> None:
		"""Setup dynamic action models from controller's registry"""
		# Get the dynamic action model from controller's registry
		self.ActionModel = self.controller.registry.create_action_model()
		# Create output model with the dynamic actions
		self.AgentOutput = CustomAgentOutput.type_with_custom_actions(self.ActionModel)

	def update_step_info(
		self, model_output: CustomAgentOutput, step_info: Optional[CustomAgentStepInfo] = None
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
	async def get_next_action(self, input_messages: List[BaseMessage]) -> CustomAgentOutput:
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
		self._message_manager._add_message_with_tokens(converted_msg)

		ai_content = ai_message.replace("```json", "").replace("```", "")
		ai_content = repair_json(ai_content)
		parsed_json = json.loads(ai_content)
		parsed: AgentOutput = self.AgentOutput(**parsed_json)

		if parsed is None:
			logger.debug(ai_message.content)
			raise ValueError('Could not parse response.')

		# cut the number of actions to max_actions_per_step if needed
		if len(parsed.action) > self.settings.max_actions_per_step:
			parsed.action = parsed.action[: self.settings.max_actions_per_step]
		return parsed
	
	async def execute_ancillary_actions(self, input_messages: List[BaseMessage]):
		pass

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
			logger.info(f"📄 Result: {result[-1].extracted_content}")

		self.state.consecutive_failures = 0

	def _create_or_update_plan(self, curr_page_contents: str) -> None:
		"""Create or update the plan"""

		task_prompt = CreatePlan().invoke(
			model=self.llm,
			model_name=MODEL_NAME,
			prompt_args={
				"curr_page_contents": curr_page_contents
			}
		)

		return 

	@time_execution_async("--step")
	async def step(self, step_info: Optional[CustomAgentStepInfo] = None) -> None:
		"""Execute one step of the task"""
		logger.info(f"Step {self.state.n_steps}")
		state = None
		model_output = None
		result: list[ActionResult] = []
		step_start_time = time.time() 
		tokens = 0
		browser_actions: Optional[BrowserActions] = None
		curr_page: str = ""
		curr_url: str = ""

		try:    
			state = await self.browser_context.get_state()
			browser_actions = BrowserActions()

			await self._raise_if_stopped_or_paused()
			self._message_manager.add_state_message(
				state, 
				self.state.last_action, 
				self.state.last_result, 
				self.step_http_msgs,
				step_info=step_info, 
				use_vision=self.settings.use_vision
			)
			input_messages = self._message_manager.get_messages()
			tokens = self._message_manager.state.history.current_tokens
			try:
				# HACK
				for msg in input_messages:
					msg.type = ""
				model_output = await self.get_next_action(input_messages)

				# TODO: execute ancillary actions
				# await self.execute_ancillary_actions(input_messages)
						
				self.update_step_info(model_output, step_info)
				self.state.n_steps += 1
				await self._raise_if_stopped_or_paused()
			except Exception as e:
				# model call failed, remove last state message from history
				self._message_manager._remove_state_message_by_index(-1)
				raise e
 
			result: list[ActionResult] = await self.multi_act(model_output.action)
			# TODO: error handling is questionable here
			# ideally, we should be assigning ID to browser_actions and checking against
			# server for dedup
			curr_page = state.element_tree.clickable_elements_to_string()
			# is_new_page = self._is_new_page(prev_page, curr_page)

			curr_url = (await self.browser_context.get_current_page()).url
			# logger.info(f"Curr_url:{curr_url}, prev_url: {prev_url}, is_new_page: {is_new_page}")

			prev_url = curr_url
			prev_page = curr_page

			http_msgs = await self.http_handler.flush()
			self.step_http_msgs = self.http_history.filter_http_messages(http_msgs)
			browser_actions = BrowserActions(
				actions=model_output.action,
				thought=model_output.current_state.thought,
				goal=model_output.current_state.next_goal, 
			)
			if self.agent_client:
				await self._update_server(self.step_http_msgs, browser_actions)
			
			self._update_state(result, model_output, step_info)
			self._log_response(
				self.step_http_msgs,
				current_msg=input_messages[-1],
				response=model_output
			)

		except InterruptedError:
			logger.debug("Agent paused")
			self.state.last_result = [
				ActionResult(
					error="The agent was paused - now continuing actions might need to be repeated",
					include_in_memory=True
				)
			]
			return

		# except (ValidationError, ValueError, RateLimitError, ResourceExhausted) as e:
		#     result = await self._handle_step_error(e)
		#     self.state.last_result = result

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
				json_msgs = [await msg.to_json() for msg in self.step_http_msgs]
				self._make_history_item(model_output, state, result, json_msgs, metadata=metadata)

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

			try:
				if not self.injected_browser_context or self.close_browser:
					logger.info("Closing browser context")
					await self.browser_context.close()

				if (not self.injected_browser and self.browser) or (self.close_browser and self.browser):
					logger.info("Closing browser")
					await self.browser.close()
			except TargetClosedError as e:
				pass

			if self.settings.generate_gif:
				output_path: str = 'agent_history.gif'
				if isinstance(self.settings.generate_gif, str):
					output_path = self.settings.generate_gif

				create_history_gif(task=self.task, history=self.state.history, output_path=output_path)
			
			logger.info("Graceful exit!")

	async def shutdown(self, reason: str = "Premature shutdown requested") -> None:
		"""Shuts down the agent prematurely and performs cleanup."""
		# Check if already stopped to prevent duplicate shutdown calls
		if hasattr(self.state, 'stopped') and self.state.stopped:
			logger.warning("Shutdown already in progress or completed.")
			return

		logger.info(f"Initiating premature shutdown: {reason}")
		# Ensure state has 'stopped' attribute before setting
		if hasattr(self.state, 'stopped'):
			 self.state.stopped = True
		else:
			 # If AgentState doesn't have stopped, we might need another way
			 # to signal termination or handle this case.
			 logger.warning("Agent state does not have 'stopped' attribute. Cannot signal stop.")


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
					logger.info(f"Saved agent history to {self.history_file} during shutdown.")
				except Exception as e:
					logger.error(f"Failed to save history during shutdown: {e}")

			# Close Browser Context
			if not self.injected_browser_context and self.browser_context:
				try:
					await self.browser_context.close()
					logger.info("Closed browser context during shutdown.")
				except Exception as e:
					logger.error(f"Error closing browser context during shutdown: {e}")

			# Close Browser
			if self.browser:
				try:
					await self.browser.close()
					logger.info("Closed browser during shutdown.")
				except Exception as e:
					logger.error(f"Error closing browser during shutdown: {e}")

			# Generate GIF
			if self.settings.generate_gif and history:
				try:
					output_path: str = 'agent_history_shutdown.gif' # Default name
					if isinstance(self.settings.generate_gif, str):
						# Create a shutdown-specific name based on config
						base, ext = os.path.splitext(self.settings.generate_gif)
						output_path = f"{base}_shutdown{ext}"

					logger.info(f"Generating shutdown GIF at {output_path}")
					create_history_gif(task=f"{self.task} (Shutdown)", history=history, output_path=output_path)
				except Exception as e:
					 logger.error(f"Failed to generate GIF during shutdown: {e}")
			
		except Exception as e:
			# Catch errors during the shutdown cleanup process itself
			logger.error(f"Error during agent shutdown cleanup: {e}")
			logger.error(traceback.format_exc())
		finally:
			 logger.info("Agent shutdown process complete.")
