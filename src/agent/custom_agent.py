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
from langchain_core.messages import BaseMessage, AIMessage
from browser_use.browser.views import BrowserState

from json_repair import repair_json
from src.utils.agent_state import AgentState
from src.agent.client import AgentClient
from src.llm_models import LLMHub
from src.agent.utils import Pages

from eval.client import AgentEvalClient

from httplib import HTTPMessage

from playwright._impl._errors import TargetClosedError
from pentest_bot.logger import get_agent_loggers


# from .state import CustomAgentOutput
from common.agent import BrowserActions
from .custom_views import CustomAgentOutput
from .custom_message_manager import CustomMessageManager, CustomMessageManagerSettings
from .custom_views import CustomAgentStepInfo, CustomAgentState
from .http_history import HTTPHistory, HTTPHandler

from .discovery import (
    # CreatePlan,
    # UpdatePlan,
    CreatePlanNested,
    UpdatePlanNested,
    CheckNestedPlanCompletion,
    CompletedNestedPlanItem,
    DetermineNewPage,
    NewPageStatus,
    NavPage,
    TASK_PROMPT_WITH_PLAN,
    Plan,
    AddPlanItemList,
    CompletedPlans
)

agent_log, full_log = get_agent_loggers()

Context = TypeVar('Context')

MODEL_NAME = "gpt-4.1"

class AgentMode(Enum):
    NAVIGATION = auto()
    TASK_EXECUTION = auto()
    START_ACTION = auto()

class Event(Enum):
    NAV_START      = auto()
    NAV_SUCCESS    = auto()
    NAV_FAILED     = auto()
    TASK_COMPLETE  = auto()
    BACKTRACK      = auto()
    PAGE_COMPLETE  = auto()
    SHUTDOWN       = auto()

TRANSITIONS = {
    (AgentMode.START_ACTION, Event.NAV_START):    AgentMode.NAVIGATION,
    (AgentMode.TASK_EXECUTION, Event.NAV_START): AgentMode.NAVIGATION, # NOT IMPLEMENTED
    (AgentMode.TASK_EXECUTION, Event.BACKTRACK):  AgentMode.NAVIGATION,
    (AgentMode.TASK_EXECUTION, Event.PAGE_COMPLETE): AgentMode.NAVIGATION,
    (AgentMode.NAVIGATION, Event.NAV_FAILED):     AgentMode.NAVIGATION, # NOT IMPLEMENTED
    (AgentMode.NAVIGATION, Event.NAV_SUCCESS):    AgentMode.TASK_EXECUTION, # need to differentiate backtrack (no plan change)
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

# TODO:
# - fix issue with TASK_EXECUTION -> NAVIGATION not marking the task as complete 
async def _create_or_update_plan(
    llm: LLMHub,
    curr_page_contents: str,
    curr_url: str,
    step_number: int,
    # New parameters - previously accessed via self.state
    prev_page_contents: str,
    prev_url: str,
    eval_prev_goal: str,
    curr_goal: str,
    curr_plan: Plan,
    # New parameters - previously accessed via self
    homepage_contents: str,
    homepage_url: str,
) -> Tuple[Optional[Event], Optional[str], Plan, Plan, Optional[NavPage]]:  # Added return values for updated plan and subpages
    """
    REMOVED STATE WRITE OPERATIONS:
    1. self.state.plan = curr_plan (line removed from original)
    2. self._set_plan(curr_plan) (line removed from original)
    3. self.subpages.append((curr_url, curr_page_contents, nav_page.name)) (line removed from original)
    
    Now returns: (event, new_task, updated_plan, updated_subpages)
    """
    new_task = None
    event = None
    old_plan = curr_plan

    completed: CompletedNestedPlanItem = CheckNestedPlanCompletion().invoke(
        model=llm.get("check_plan_completion"),
        prompt_args={
            "plan": curr_plan,
            "prev_page_contents": prev_page_contents,
            "curr_page_contents": curr_page_contents,
            "curr_goal": curr_goal
        },
        prompt_logger=full_log  
    )
    for compl in completed.plan_indices:
        curr_plan.get(compl).completed = True
        agent_log.info(f"Completed plan item: {curr_plan.get(compl).description}")    
    
    # if step_number > 1 and step_number % DEDUP_AFTER_STEPS == 0:
    # 	curr_plan = deduplicate_plan(llm, curr_plan)
    
    nav_page: NavPage = DetermineNewPage().invoke(
        model=llm.get("determine_new_page"), 
        prompt_args={
            "curr_page_contents": curr_page_contents, 
            "prev_page_contents": prev_page_contents, 
            "curr_url": curr_url, 
            "prev_url": prev_url, 
            "curr_goal": curr_goal,
            "homepage_contents": homepage_contents,
            "homepage_url": homepage_url
        },
        prompt_logger=full_log
    )
    if nav_page.status == NewPageStatus.NEW_PAGE:
        agent_log.info(f"Discovered [new_page]: {curr_url}")
        agent_log.info(f"Navigating back to homepage:{homepage_url}")
        new_task = NAVIGATE_TO_PAGE_PROMPT.format(
            curr_page_contents=curr_page_contents,
            url=homepage_url
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
                # "eval_prev_goal": eval_prev_goal
            },
            prompt_logger=full_log
        )
        new_task = TASK_PROMPT_WITH_PLAN.format(plan=curr_plan)        
    else:
        agent_log.info("No task updates")

    return event, new_task, curr_plan, old_plan, nav_page

class CustomAgent(Agent):
    def __init__(
        self,
        start_urls: List[str],
        llm: LLMHub,
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
        eval_client: Optional[AgentEvalClient] = None,
        app_id: Optional[str] = None,
        close_browser: bool = False,
        agent_name: str = ""
    ):
        start_task = start_task or NO_OP_TASK

        super(CustomAgent, self).__init__(
            task=start_task,
            llm=llm.get("browser_use"),
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
        self.llm = llm
        self.agent_name = agent_name
        self.close_browser = close_browser
        self.curr_page = None
        self.history_file = history_file
        self.http_handler = HTTPHandler()
        self.http_history = HTTPHistory()
        
        if browser_context:
            browser_context.req_handler = self.http_handler.handle_request
            browser_context.res_handler = self.http_handler.handle_response
            # browser_context.page_handler = self.handle_page

        self.state = CustomAgentState()
        self.add_infos = add_infos
        self._message_manager = CustomMessageManager(
            task=start_task,
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
        self.mode = AgentMode.START_ACTION
        self._set_task(start_task)
        self._backtrack = False

        self.step_http_msgs = []

        # every thing have some interaction with the server
        self.agent_client = agent_client
        self.app_id = app_id
        self.agent_id = None
        if agent_client and not app_id:
            raise ValueError("app_id must be provided when agent_client is set")
        
        self.subpages = []
        self.pages = Pages(items=start_urls)
        # TODO: should move this to server-side eventually to support multiple agents
        self.eval_client = eval_client
        if self.eval_client:
            self.eval_client.set_shutdown(self.shutdown)

    def handle_page(self, page):
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

        agent_log.info(f"Eval {emoji}: {response.current_state.evaluation_previous_goal}")
        agent_log.info(f"Next Goal: {response.current_state.next_goal}")
        for i, action in enumerate(response.action):
            agent_log.info(
                f"Action {i + 1}/{len(response.action)}: {action.model_dump_json(exclude_unset=True)}"
            )
        agent_log.info(f"Prev Messages]: {current_msg.content}")
        agent_log.info(f"Captured {len(http_msgs)} HTTP Messages")
        for msg in http_msgs:
            agent_log.info(f"[Agent] {msg.request.url}")

        agent_log.info(f"Current plan:\n{self._get_plan()}")
        agent_log.info(f"Pages: {self.pages}")

    def _setup_action_models(self) -> None:
        """Setup dynamic action models from controller's registry"""
        # Get the dynamic action model from controller's registry
        self.ActionModel = self.controller.registry.create_action_model()
        # Create output model with the dynamic actions
        self.AgentOutput = CustomAgentOutput.type_with_custom_actions(self.ActionModel)

    @time_execution_async("--get_next_action")
    async def get_next_action(self, input_messages: List[BaseMessage]) -> CustomAgentOutput:
        """Get next action from LLM based on current state"""
        ai_message: BaseMessage = self.llm.get("browser_use").invoke(
            input_messages,
        )
        self._message_manager._add_message_with_tokens(ai_message)

        ai_content = ai_message.content.replace("```json", "").replace("```", "")
        ai_content = repair_json(ai_content)
        parsed_json = json.loads(ai_content)
        parsed: AgentOutput = self.AgentOutput(**parsed_json)

        if parsed is None:
            agent_log.debug(ai_message.content)
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
    
    async def _get_browser_state(self):
        browser_state = await self.browser_context.get_state()
        curr_url = (await self.browser_context.get_current_page()).url
        curr_page_contents = browser_state.element_tree.clickable_elements_to_string()

        return browser_state, curr_url, curr_page_contents
    
    async def _execute_agent_step(
        self,
        browser_state: "BrowserState",
        step_info: "CustomAgentStepInfo",
    ) -> Tuple[CustomAgentOutput, List[ActionResult], List[BaseMessage]]:
        self._message_manager.add_state_message(
            self._get_task(),
            browser_state,
            self.state.last_action, 
            self.state.last_result, 
            self.step_http_msgs,
            step_info=step_info, 
            use_vision=self.settings.use_vision
        )
        input_messages = self._message_manager.get_messages()
        for i, msg in enumerate(input_messages, start=1):
            agent_log.info(f"==========[INPUT] {i}==========")
            agent_log.info(f"{msg.content}")
            
        agent_log.info(f"[INPUT]: Input messages len {len(input_messages)}")
        for msg in input_messages:
            agent_log.info(f"[INPUT] {msg.content}")
        try:
            # HACK
            for msg in input_messages:
                msg.type = ""
            model_output = await self.get_next_action(input_messages)

            step_info.step_number += 1
            step_info.page_step_number += 1
            self.state.n_steps += 1
            self._message_manager._remove_last_human_message()

            await self._raise_if_stopped_or_paused()
        except Exception as e:
            # model call failed, remove last state message from history
            self._message_manager._remove_state_message_by_index(-1)
            raise e

        result = await self.multi_act(model_output.action)
        return model_output, result, input_messages
    
    async def _nav_think(self, model_output: CustomAgentOutput, step_info: CustomAgentStepInfo):
        # if not self.ctx.pages:
        # 	raise EarlyShutdown("No pages queued for navigation")

        eval_str = model_output.current_state.evaluation_previous_goal.lower()
        failed   = ("failed" in eval_str) or ("unknown" in eval_str and step_info.step_number > 2)
        event    = Event.NAV_FAILED if failed else Event.NAV_SUCCESS
        return event

    async def _task_think(self, page_contents: str, url: str, step_info: CustomAgentStepInfo, model_output: CustomAgentOutput):
        curr_plan = self._get_plan()
        if curr_plan is None:
            raise EarlyShutdown("No plan found, should not happen")

        event, new_task, new_plan, old_plan, nav_page = await _create_or_update_plan(
            llm=self.llm,
            curr_page_contents=page_contents,
            curr_url=url,
            step_number=step_info.step_number,
            # Parameters from self.state
            prev_page_contents=self.state.prev_page_contents,
            prev_url=self.state.prev_url,
            eval_prev_goal=model_output.current_state.evaluation_previous_goal,
            curr_goal=model_output.current_state.next_goal,
            curr_plan=curr_plan,
            # Parameters from self
            homepage_contents=self.homepage_contents,
            homepage_url=self.homepage_url,
        )
        if event == Event.BACKTRACK:
            self._backtrack = True
            self._replace_plan = old_plan

        return event, new_task, new_plan, nav_page

    # NOTE: should not use state here??
    async def _transition(
        self, 
        step_info: CustomAgentStepInfo,
        event: Event | None,
        new_url: str, 
        new_page_contents: str,
        new_plan: Plan | None = None,
        new_task: str | None = None,
        nav_page: NavPage | None = None,
    ) -> None:
        """Do all task transitions and updates to page structure here"""
        if event is None:
            agent_log.info(f"No transition staying in {self.mode}")
            # TODO: having this here is ideal but dont see a way if we want to keep all task updates
            # in transition
            if self.mode is AgentMode.TASK_EXECUTION and new_task:
                self._set_task(new_task, is_new_task=False)
                self._set_plan(new_plan)
                if nav_page:
                    self.subpages.append(nav_page.name)

            next_mode = self.mode
        else:
            next_mode = TRANSITIONS.get((self.mode, event))
            agent_log.info(f"{self.mode} -[{event}]-> {next_mode}")
            self.mode = next_mode
            if next_mode is AgentMode.NAVIGATION:
                if event in [Event.NAV_START, Event.PAGE_COMPLETE]:
                    target = self.pages.pop()
                    agent_log.info(f"Starting at new page: {target}")
                    task = NAVIGATE_TO_PAGE_PROMPT.format(
                        curr_page_contents=new_page_contents,
                        url=target
                    )
                    self._set_task(task, is_new_task=True)
                    if event == Event.PAGE_COMPLETE:
                        agent_log.info(f"[PAGE] Page transition to {target} complete")
                        step_info.page_step_number = 0
                        self._backtrack = False
                elif event == Event.BACKTRACK:
                    self.pages.add(new_url)
                    self._set_task(new_task, is_new_task=True)
            elif next_mode is AgentMode.TASK_EXECUTION:
                if event == Event.NAV_SUCCESS:
                    self.homepage_url = new_url
                    self.homepage_contents = new_page_contents
                    
                    # FEAT: initialize the page here

        
                    # SPECIAL CASE: replace task with original after navigation finished instead of creating new one
                    # TODO: having _backtrack as additional transition state edge is not ideal ...
                    if not self._backtrack:
                        agent_log.info("Creating new plan")
                        new_plan = CreatePlanNested().invoke(
                            model=self.llm.get("create_plan"),
                            prompt_args={
                                "curr_page_contents": new_page_contents
                            },
                            prompt_logger=full_log
                        )
                        self._set_plan(new_plan)
                        new_task = TASK_PROMPT_WITH_PLAN.format(plan=new_plan)
                        self._set_task(new_task, is_new_task=True)
                    else:
                        agent_log.info("Backtracking, replacing plan with original")
                        self._set_plan(self._replace_plan)
                        new_task = TASK_PROMPT_WITH_PLAN.format(plan=self._replace_plan)
                        self._set_task(new_task, is_new_task=True)

        self.mode = next_mode

    def _set_plan(self, plan: Plan) -> None:
        full_log.info(f"[NEW PLAN]:\n{plan}")
        self.state.plan = plan

    def _get_plan(self) -> Optional[Plan]:
        return self.state.plan

    def _set_task(self, task: str, is_new_task: bool = False) -> None:
        self.state.task = task            

    def _get_task(self) -> str:
        return self.state.task

    async def _update_state(
        self,
        result: list,
        model_output: CustomAgentOutput,
        step_info,
        input_messages: list,
        new_url: str,
        new_page_contents: str,
    ) -> None:
        self.state.prev_goal = model_output.current_state.next_goal
        self.state.eval_prev_goal = model_output.current_state.evaluation_previous_goal
        self.state.prev_url = new_url
        self.state.prev_page_contents = new_page_contents

        http_msgs = await self.http_handler.flush()
        self.step_http_msgs = self.http_history.filter_http_messages(http_msgs)
        browser_actions = BrowserActions(
            actions=model_output.action,
            goal=model_output.current_state.next_goal, 
        )
        if self.agent_client:
            await self._update_server(self.step_http_msgs, browser_actions)
        
        # TODO: check if we really need all of this
        # random state update stuff ...
        self.state.last_result = result
        self.state.last_action = model_output.action
        self.state.consecutive_failures = 0

        self._log_response(
            self.step_http_msgs,
            current_msg=input_messages[-1],
            response=model_output
        )

    @time_execution_async("--step")
    async def step(self, step_info: CustomAgentStepInfo) -> None:
        """Execute one step of the task"""
        agent_log.info(f"-------[Step {self.state.n_steps}]-------")
        full_log.info(f"-------[Step {self.state.n_steps}]-------")
        model_output = None
        result: List[ActionResult] = []
        step_start_time = time.time() 
        tokens = 0

        try:    
            # TODO: do we need this?
            # await self._raise_if_stopped_or_paused()
            browser_state, curr_url, curr_page_contents = await self._get_browser_state()
            model_output, result, input_messages = await self._execute_agent_step(browser_state, step_info)
            new_browser_state, new_url, new_page_contents = await self._get_browser_state()

            new_task = None
            new_plan = None
            nav_page = None
            evt = None

            # Always complete the start action before page transition
            if self.mode == AgentMode.START_ACTION and result[-1].is_done:
                agent_log.info("START ACTION COMPLETED!")
                evt = Event.NAV_START
            else:
                if step_info.page_step_number >= step_info.page_max_steps:
                    evt = Event.PAGE_COMPLETE
                else:
                    if self.mode == AgentMode.NAVIGATION:
                        evt = await self._nav_think(model_output, step_info)
                    elif self.mode == AgentMode.TASK_EXECUTION:
                        evt, new_task, new_plan, nav_page = await self._task_think(new_page_contents, new_url, step_info, model_output)

            await self._update_state(result, model_output, step_info, input_messages, new_url, new_page_contents)
            await self._transition(step_info, evt, new_url, new_page_contents, new_plan, new_task, nav_page)

            if self.eval_client:
                self.eval_client.update_status(http_msgs=self.step_http_msgs)

        except InterruptedError:
            agent_log.debug("Agent paused")
            self.state.last_result = [
                ActionResult(
                    error="The agent was paused - now continuing actions might need to be repeated",
                    include_in_memory=True
                )
            ]
            return

        except Exception as e:
            agent_log.error(f"Error in step {self.state.n_steps}: {e}")
            agent_log.error(traceback.format_exc())
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

    async def run(self, max_steps: int, page_max_steps: int) -> AgentHistoryList:
        """Execute the task with maximum number of steps"""
        try:    
            # sys_msgs = self.message_manager.get_messages()
            # full_log.info(f"Sytem prompt:")
            # for msg in sys_msgs:
            #     full_log.info(msg.content)

            # self._log_agent_run()

            # Execute initial actions if provided
            if self.initial_actions:
                result = await self.multi_act(self.initial_actions, check_for_new_elements=False)
                self.state.last_result = result

            step_info = CustomAgentStepInfo(
                step_number=1,
                page_step_number=1,
                max_steps=max_steps,
                page_max_steps=page_max_steps,
            )

            for step in range(max_steps):
                # Check if we should stop due to too many failures
                if self.state.consecutive_failures >= self.settings.max_failures:
                    agent_log.error(f'❌ Stopping due to {self.settings.max_failures} consecutive failures')
                    break

                # Check control flags before each step
                if self.state.stopped:
                    agent_log.info('Agent stopped')
                    break

                while self.state.paused:
                    await asyncio.sleep(0.2)  # Small delay to prevent CPU spinning
                    if self.state.stopped:  # Allow stopping while paused
                        break

                await self.step(step_info)    
                # TODO: disabled task completion check for now
                # if self.state.history.is_done():
                # 	if selft await self._validate_output():
                # 			co.settings.validate_output and step < max_steps - 1:
                # 		if nontinue

                # 	await self.log_completion()
                # 	break
            else:
                agent_log.info("❌ Failed to complete task in maximum steps")

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
                    agent_log.info("Closing browser context")
                    await self.browser_context.close()

                if (not self.injected_browser and self.browser) or (self.close_browser and self.browser):
                    agent_log.info("Closing browser")
                    await self.browser.close()
            except TargetClosedError as e:
                pass

            if self.settings.generate_gif:
                output_path: str = 'agent_history.gif'
                if isinstance(self.settings.generate_gif, str):
                    output_path = self.settings.generate_gif

                create_history_gif(task=self.task, history=self.state.history, output_path=output_path)
            
            if self.eval_client:
                _, progress_str = self.eval_client.report_progress()
                agent_log.info("Eval results:")
                agent_log.info(progress_str)
            

            agent_log.info("===== LLM Cost Breakdown =====")
            costs = self.llm.get_costs()
            total_cost = sum(costs.values())
            n_steps = getattr(self.state, "n_steps", 0)
            avg_cost_per_step = total_cost / n_steps if n_steps > 0 else 0.0

            agent_log.info("Cost per function:")
            for func, cost in costs.items():
                agent_log.info(f"  {func}: ${cost:.6f}")
            agent_log.info(f"Total cost: ${total_cost:.6f}")
            agent_log.info(f"Average cost per step: ${avg_cost_per_step:.6f}")

            agent_log.info("======= [le fin] ========")

    async def shutdown(self, reason: str = "Premature shutdown requested") -> None:
        """Shuts down the agent prematurely and performs cleanup."""
        # Check if already stopped to prevent duplicate shutdown calls
        if hasattr(self.state, 'stopped') and self.state.stopped:
            agent_log.warning("Shutdown already in progress or completed.")
            return

        agent_log.info(f"Initiating premature shutdown: {reason}")
        # Ensure state has 'stopped' attribute before setting
        if hasattr(self.state, 'stopped'):
             self.state.stopped = True
        else:
             # If AgentState doesn't have stopped, we might need another way
             # to signal termination or handle this case.
             agent_log.warning("Agent state does not have 'stopped' attribute. Cannot signal stop.")


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
                    agent_log.info(f"Saved agent history to {self.history_file} during shutdown.")
                except Exception as e:
                    agent_log.error(f"Failed to save history during shutdown: {e}")

            # Close Browser Context
            if not self.injected_browser_context and self.browser_context:
                try:
                    await self.browser_context.close()
                    agent_log.info("Closed browser context during shutdown.")
                except Exception as e:
                    agent_log.error(f"Error closing browser context during shutdown: {e}")

            # Close Browser
            if self.browser:
                try:
                    await self.browser.close()
                    agent_log.info("Closed browser during shutdown.")
                except Exception as e:
                    agent_log.error(f"Error closing browser during shutdown: {e}")

            # Generate GIF
            if self.settings.generate_gif and history:
                try:
                    output_path: str = 'agent_history_shutdown.gif' # Default name
                    if isinstance(self.settings.generate_gif, str):
                        # Create a shutdown-specific name based on config
                        base, ext = os.path.splitext(self.settings.generate_gif)
                        output_path = f"{base}_shutdown{ext}"

                    agent_log.info(f"Generating shutdown GIF at {output_path}")
                    create_history_gif(task=f"{self.task} (Shutdown)", history=history, output_path=output_path)
                except Exception as e:
                     agent_log.error(f"Failed to generate GIF during shutdown: {e}")
            
        except Exception as e:
            # Catch errors during the shutdown cleanup process itself
            agent_log.error(f"Error during agent shutdown cleanup: {e}")
            agent_log.error(traceback.format_exc())
        finally:
             agent_log.info("Agent shutdown process complete.")
