from __future__ import annotations

import logging
from typing import List, Type, Optional

from browser_use.agent.message_manager.service import MessageManager
from browser_use.agent.views import ActionResult, ActionModel
from browser_use.browser.views import BrowserState
from browser_use.agent.message_manager.service import MessageManagerSettings
from browser_use.agent.views import ActionResult, MessageManagerState
from langchain_core.messages import (
    HumanMessage,
    SystemMessage
)
from httplib import HTTPMessage

from .custom_prompts import CustomAgentMessagePrompt
from .custom_views import CustomAgentStepInfo
from .custom_prompts import CustomAgentMessagePrompt

logger = logging.getLogger(__name__)


class CustomMessageManagerSettings(MessageManagerSettings):
    agent_prompt_class: Type[CustomAgentMessagePrompt] = CustomAgentMessagePrompt

class CustomMessageManager(MessageManager):
    def __init__(
            self,
            task: str,
            system_message: SystemMessage,
            settings: CustomMessageManagerSettings = CustomMessageManagerSettings(),
            state: MessageManagerState = MessageManagerState(),
    ):
        super().__init__(
            task=task,
            system_message=system_message,
            settings=settings,
            state=state
        )
        self.settings: CustomMessageManagerSettings

    def _init_messages(self) -> None:
        """Initialize the message history with system message, context, task, and other initial messages"""
        self._add_message_with_tokens(self.system_prompt)
        self.context_content = ""

        if self.settings.message_context:
            self.context_content += 'Context for the task' + self.settings.message_context

        if self.settings.sensitive_data:
            info = f'Here are placeholders for sensitive data: {list(self.settings.sensitive_data.keys())}'
            info += 'To use them, write <secret>the placeholder name</secret>'
            self.context_content += info

        if self.settings.available_file_paths:
            filepaths_msg = f'Here are file paths you can use: {self.settings.available_file_paths}'
            self.context_content += filepaths_msg

        if self.context_content:
            context_message = HumanMessage(content=self.context_content)
            self._add_message_with_tokens(context_message)

    def cut_messages(self):
        """Get current message list, potentially trimmed to max tokens"""
        diff = self.state.history.current_tokens - self.settings.max_input_tokens
        min_message_len = 2 if self.context_content is not None else 1

        while diff > 0 and len(self.state.history.messages) > min_message_len:
            self.state.history.remove_message(min_message_len)  # always remove the oldest message
            diff = self.state.history.current_tokens - self.settings.max_input_tokens

    # AFTER DINNER:
    # - wire up HTTP_msgs everywhere
    def add_state_message(
        self,
        task: str,
        state: BrowserState,
        actions: List[ActionModel],
        result: List[ActionResult],
        http_msgs: List[HTTPMessage],
        step_info: Optional[CustomAgentStepInfo] = None,
        use_vision=True,
    ) -> None:
        """Add browser state as human message"""
        # otherwise add state message and result to next message (which will not stay in memory)
        state_message = self.settings.agent_prompt_class(
            task,
            state,
            actions,
            result,
            self.settings.include_attributes,
            http_msgs,
            step_info,
        ).get_user_message(use_vision)
        self._add_message_with_tokens(state_message)

    def _remove_state_message_by_index(self, remove_ind=-1) -> None:
        """Remove last state message from history"""
        i = len(self.state.history.messages) - 1
        remove_cnt = 0
        while i >= 0:
            if isinstance(self.state.history.messages[i].message, HumanMessage):
                remove_cnt += 1
            if remove_cnt == abs(remove_ind):
                self.state.history.messages.pop(i)
                break
            i -= 1

    def _remove_last_human_message(self):
        """Remove the last HumanMessage from history"""
        for i in range(len(self.state.history.messages) - 1, -1, -1):
            if isinstance(self.state.history.messages[i].message, HumanMessage):
                self.state.history.messages.pop(i)
                break