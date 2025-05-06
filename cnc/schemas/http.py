from typing import Optional, List
from pydantic import BaseModel
from httplib import HTTPRequest, HTTPMessage, ResourceLocator, AuthSession

class EnrichAuthNZMessage(BaseModel):
    http_msg: HTTPMessage
    username: str
    role: Optional[str] = ""

class EnrichedRequest(BaseModel):
    request: HTTPRequest
    username: Optional[str] = None
    role: Optional[str] = None
    session: Optional[AuthSession] = None
    resource_locators: Optional[List[ResourceLocator]] = None