from pydantic import BaseModel
from typing import List, Optional

from browser_use import ActionModel

class UserCreds(BaseModel):
    user_name: str
    role: str

class BrowserActions(BaseModel):
    actions: Optional[List[ActionModel]] = []
    thought: Optional[str] = ""
    goal: Optional[str] = ""