from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Type
import uuid

from browser_use.agent.views import AgentOutput, AgentState, ActionResult, AgentHistoryList, MessageManagerState
from browser_use.controller.registry.views import ActionModel
from pydantic import BaseModel, ConfigDict, Field, create_model


@dataclass
class CustomAgentStepInfo:
    step_number: int
    max_steps: int
    task: str
    add_infos: str
    memory: str


class CustomAgentBrain(BaseModel):
    """Current state of the agent"""

    evaluation_previous_goal: str
    important_contents: str
    thought: str
    next_goal: str

    def to_prompt(self) -> str:
        return (
            f"Evaluation: {self.evaluation_previous_goal}\n"
            f"Important Contents: {self.important_contents}\n"
            f"Thought: {self.thought}\n"
            f"Next Goal: {self.next_goal}"
        )
    
class CustomAgentOutput(AgentOutput):
    """Output model for agent

    @dev note: this model is extended with custom actions in AgentService. You can also use some fields that are not in this model as provided by the linter, as long as they are registered in the DynamicActions model.
    """

    current_state: CustomAgentBrain
 
    @staticmethod
    def type_with_custom_actions(
            custom_actions: Type[ActionModel],
    ) -> Type["CustomAgentOutput"]:
        """Extend actions with custom actions"""
        model_ = create_model(
            "CustomAgentOutput",
            __base__=CustomAgentOutput,
            action=(
                list[custom_actions],
                Field(..., description='List of actions to execute', json_schema_extra={'min_items': 1}),
            ),  # Properly annotated field with no default
            __module__=CustomAgentOutput.__module__,
        )
        model_.__doc__ = 'AgentOutput model with custom actions'
        return model_

    def to_prompt(self) -> str:
        actions_str = "\n".join(
            f"Action {i+1}: {action}" 
            for i, action in enumerate(self.action)
        )
        return (
            f"Current State:\n{self.current_state.to_prompt()}\n"
            f"Actions:\n{actions_str}"
        )

class CustomAgentState(BaseModel):
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    n_steps: int = 1
    consecutive_failures: int = 0
    last_result: Optional[List['ActionResult']] = Field(default_factory=list)
    history: AgentHistoryList = Field(default_factory=lambda: AgentHistoryList(history=[]))
    last_plan: Optional[str] = None
    paused: bool = False
    stopped: bool = False

    message_manager_state: MessageManagerState = Field(default_factory=MessageManagerState)

    last_action: Optional[List['ActionModel']] = None
    extracted_content: str = ''
