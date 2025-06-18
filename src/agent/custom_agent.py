import json
import traceback
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Type, TypeVar, Set, Deque, Tuple
import os
import asyncio
import time
from enum import Enum, auto
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

from json_repair import repair_json
from src.utils.agent_state import AgentState
from src.agent.client import AgentClient

from johnllm import LLMModel, LMP
from httplib import HTTPMessage

from playwright._impl._errors import TargetClosedError
from logging import getLogger
from logger import init_root_logger

# from .state import CustomAgentOutput
from common.agent import BrowserActions
from .custom_views import CustomAgentOutput
from .custom_message_manager import CustomMessageManager, CustomMessageManagerSettings
from .custom_views import CustomAgentStepInfo, CustomAgentState
from .http_history import HTTPHistory, HTTPHandler, BAN_LIST
from .logger import AgentLogger

from .discovery import (
	CreatePlan,
	TASK_PROMPT_WITH_PLAN
)

logger = getLogger(__name__)

Context = TypeVar('Context')

MODEL_NAME = "gpt-4.1"

class AgentMode(Enum):
	NAVIGATION = auto()
	TASK_EXECUTION = auto()
	NOOP = auto()

class Event(Enum):
	NOOP_NAV	   = auto()
	NAV_SUCCESS    = auto()
	NAV_FAILED     = auto()
	TASK_COMPLETE  = auto()
	BACKTRACK      = auto()
	SHUTDOWN       = auto()

TRANSITIONS = {
	(AgentMode.NOOP, Event.NOOP_NAV):    AgentMode.NAVIGATION,
	(AgentMode.NAVIGATION, Event.NAV_SUCCESS):    AgentMode.TASK_EXECUTION,
	(AgentMode.NAVIGATION, Event.NAV_FAILED):     AgentMode.NAVIGATION,
	(AgentMode.TASK_EXECUTION, Event.TASK_COMPLETE): AgentMode.NAVIGATION,
	(AgentMode.TASK_EXECUTION, Event.BACKTRACK):  AgentMode.NAVIGATION,
}

NO_OP_TASK = """
This is a no-op task. The agent will not take any action

Make sure to:
- automatically evaluate this current task as successful by the next agentic step
"""

NAVIGATE_TO_PAGE_PROMPT = """
Navigate to the following page:

{url}

First, determine if its possible to navigate to the page through UI interactions
If so, do that. If not, use the goto action to perform the navigation
"""

class CustomAgent(Agent):
	def __init__(
		self,
		start_url: str,
		llm: LLMModel,
		start_task: str = "", # TODO: task for handling all initial logic
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
		available_file_paths: Optional[List[str]] = None,
		include_attributes: List[str] = [
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
			task=NO_OP_TASK,
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

		if browser_context:
			logger.info("Registering HTTP handlers")
			browser_context.req_handler = self.http_handler.handle_request
			browser_context.res_handler = self.http_handler.handle_response
			# browser_context.page_handler = self.handle_page

		self.state = CustomAgentState()
		self.add_infos = add_infos
		self._message_manager = CustomMessageManager(
			task=NO_OP_TASK,
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

		self.step_http_msgs = []
		self.mode = AgentMode.NOOP
		self.pages = [start_url]
		self.subpages = []
		self._set_task(NO_OP_TASK)

	def handle_page(self, page):
		logger.info(f"[PLAYWRIGHT] >>>>>>>>>>>")
		logger.info(f"[PLAYWRIGHT] Frame {page}")
		self.curr_page = page
		
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
	
	async def _get_browser_state(self):
		browser_state = await self.browser_context.get_state()
		curr_url = (await self.browser_context.get_current_page()).url
		curr_page_contents = browser_state.element_tree.clickable_elements_to_string()

		return browser_state, curr_url, curr_page_contents
	
	async def _execute_agent_step(
		self,
		browser_state: "BrowserState",
		curr_url: str,
		curr_page_contents: str,
		step_info: "CustomAgentStepInfo",
	) -> Tuple[CustomAgentOutput, List[ActionResult], List[BaseMessage]]:
		self._message_manager.add_state_message(
			self.state.task,
			browser_state, 
			self.state.last_action, 
			self.state.last_result, 
			self.step_http_msgs,
			step_info=step_info, 
			use_vision=self.settings.use_vision
		)
		input_messages = self._message_manager.get_messages()
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
			self._message_manager._remove_state_message_by_index(-1)
			raise e

		result = await self.multi_act(model_output.action)
		return model_output, result, input_messages
	
	async def _nav_think(self, model_output: CustomAgentOutput, step_info: CustomAgentStepInfo):
		# # Ensure we hold a goal page
		# if not self.ctx.pages:
		# 	raise EarlyShutdown("No pages queued for navigation")

		# target = self.ctx.pages[-1]			# peek
		# self.ctx.homepage_url = target		# keep canonical target
		# task_prompt = NAVIGATE_TO_PAGE_PROMPT.format(url=target)

		# model_output = await self._invoke_llm(state, task_prompt)

		# Decide event using previous evaluation string (no writes yet)
		eval_str = model_output.current_state.evaluation_previous_goal.lower()
		failed   = ("failed" in eval_str) or ("unknown" in eval_str and step_info.step_number > 2)
		event    = Event.NAV_FAILED if failed else Event.NAV_SUCCESS
		return event

	async def _task_think(self, state, html, url, info):
		# # Plan management
		# task_prompt, replace_task, evt = await self._plan_update(html, url, info.step_number)
		# if replace_task:			# back-navigation case
		# 	self.state.task = replace_task

		# model_output = await self._invoke_llm(state, task_prompt)

		# if evt:						# NEW_PAGE/BACKTRACK already decided
		# 	return evt, model_output

		# plan_done = self._plan_complete(self.ctx.plan)
		# if plan_done or info.page_steps >= self.page_max_steps:
		# 	return Event.TASK_COMPLETE, model_output

		# return None, model_output	# remain in TASK_EXECUTION
		pass

	async def _transition(self, event: Event | None) -> None:
		if event is None:
			return

		next_mode = TRANSITIONS.get((self.mode, event))
		if next_mode is None:
			logger.info(f"[TRANSITION] No transition staying in {self.mode}")
			return
 
		logger.info(f"[TRANSITION] {self.mode} -> {next_mode}")
		self.mode = next_mode

		if next_mode is AgentMode.NAVIGATION:
			# Pop next target, build nav task
			target = self.pages.pop()
			task = NAVIGATE_TO_PAGE_PROMPT.format(url=target)
			self._set_task(task)
			
		self.mode = next_mode

	# Managing setting and getting the task
	def _set_task(self, task: str) -> None:
		self.state.task = task

	def _get_task(self) -> str:
		return self.state.task

	async def _update_state(
		self,
		result: list,
		model_output,
		step_info,
		input_messages: list,
	) -> None:
		http_msgs = await self.http_handler.flush()
		self.step_http_msgs = self.http_history.filter_http_messages(http_msgs)
		browser_actions = BrowserActions(
			actions=model_output.action,
			thought=model_output.current_state.thought,
			goal=model_output.current_state.next_goal, 
		)
		if self.agent_client:
			await self._update_server(self.step_http_msgs, browser_actions)
		
		# TODO: check if we really need all of this
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

		self._log_response(
			self.step_http_msgs,
			current_msg=input_messages[-1],
			response=model_output
		)

	@time_execution_async("--step")
	async def step(self, step_info: CustomAgentStepInfo) -> None:
		"""Execute one step of the task"""
		logger.info(f"Step {self.state.n_steps}")
		model_output = None
		result: List[ActionResult] = []
		step_start_time = time.time() 
		tokens = 0
		curr_page: str = ""
		curr_url: str = ""

		try:    
			# TODO: do we need this?
			# await self._raise_if_stopped_or_paused()
			browser_state, curr_url, curr_page_contents = await self._get_browser_state()
			model_output, result, input_messages = await self._execute_agent_step(
				browser_state, 
				curr_url, 
				curr_page_contents, 
				step_info
			)
			new_browser_state, new_url, new_page_contents = await self._get_browser_state()

			if self.mode == AgentMode.NAVIGATION:
				evt = await self._nav_think(model_output, step_info)
			elif self.mode == AgentMode.TASK_EXECUTION:
				await self._task_think(self.state, new_page_contents, new_url, step_info)
			elif self.mode == AgentMode.NOOP:
				evt = Event.NOOP_NAV

			await self._transition(evt)
			await self._update_state(result, model_output, step_info, input_messages)

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

			if browser_state:
				metadata = StepMetadata(
					step_number=self.state.n_steps,
					step_start_time=step_start_time,
					step_end_time=step_end_time,
					input_tokens=tokens,
				)
				json_msgs = [await msg.to_json() for msg in self.step_http_msgs]
				self._make_history_item(model_output, browser_state, result, json_msgs, metadata=metadata)

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

				# TODO: disabled task completion check for now
				# if self.state.history.is_done():
				# 	if self.settings.validate_output and step < max_steps - 1:
				# 		if not await self._validate_output():
				# 			continue

				# 	await self.log_completion()
				# 	break
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
