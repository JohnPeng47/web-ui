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

class CustomAgentOutput(BaseModel):
    current_state: CurrentState
    action: List[Dict[str, Dict[str, Union[str, int, bool]]]]
