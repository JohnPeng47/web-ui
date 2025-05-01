from typing import Optional
from pydantic import BaseModel
from httplib import HTTPRequest, HTTPMessage

class EnrichAuthNZMessage(BaseModel):
    http_msg: HTTPMessage
    username: str
    role: Optional[str] = ""

class EnrichedRequest(BaseModel):
    request: HTTPRequest
    username: Optional[str] = None
    role: Optional[str] = None
    session_id: Optional[str] = None