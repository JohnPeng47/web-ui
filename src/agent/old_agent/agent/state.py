from pydantic import BaseModel, Field
from typing import List, Dict, Union, Optional

class CurrentState(BaseModel):
    evaluation_previous_goal: str = Field(
        description="Success|Failed|Unknown - Analysis of previous goals/actions success"
    )
    important_contents: str = Field(
        description="Important contents related to user's instruction on current page"
    )
    thought: str = Field(
        description="Analysis of completed requirements and next requirements"
    )
    next_goal: str = Field(
        description="Brief natural language description of next action goals"
    )

    def to_prompt(self) -> str:
        return (
            f"Evaluation: {self.evaluation_previous_goal}\n"
            f"Important Contents: {self.important_contents}\n"
            f"Thought: {self.thought}\n"
            f"Next Goal: {self.next_goal}"
        )

class CustomAgentOutput(BaseModel):
    current_state: CurrentState
    action: List[Dict[str, Dict[str, Union[str, int, bool]]]]

    def to_prompt(self) -> str:
        actions_str = "\n".join(
            f"Action {i+1}: {action}" 
            for i, action in enumerate(self.action)
        )
        return (
            f"Current State:\n{self.current_state.to_prompt()}\n"
            f"Actions:\n{actions_str}"
        )
