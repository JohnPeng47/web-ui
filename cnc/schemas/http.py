from typing import Dict, Optional, Any
from pydantic import BaseModel, HttpUrl, PositiveInt


class HTTPRequestData(BaseModel):
    method: str
    url: HttpUrl
    headers: Dict[str, str]
    post_data: Optional[Dict[str, Any]] = None
    redirected_from_url: Optional[HttpUrl] = None
    redirected_to_url: Optional[HttpUrl] = None
    is_iframe: bool = False


class HTTPResponseData(BaseModel):
    url: HttpUrl
    status: PositiveInt
    headers: Dict[str, str]
    is_iframe: bool
    body_b64: Optional[str] = None  # keep binary safe
    body_error: Optional[str] = None


class HTTPMessage(BaseModel):
    request: HTTPRequestData
    response: Optional[HTTPResponseData] = None


class EnrichedRequest(BaseModel):
    request: HTTPRequestData
    username: Optional[str] = None
    role: Optional[str] = None
    session_id: Optional[str] = None