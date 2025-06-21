from pydantic import BaseModel, Field
from typing import List, Optional

from browser_use import ActionModel

class UserCreds(BaseModel):
    user_name: str
    role: str

class BrowserActions(BaseModel):
    is_new_page: bool = False
    page_content: str = ""
    page_url: str = ""
    actions: Optional[List[ActionModel]] = Field(default_factory=list)
    goal: Optional[str] = ""