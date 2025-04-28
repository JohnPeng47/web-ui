from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel


class RequestPart(str, Enum):
    URL = "url"
    HEADER = "header"
    BODY = "body"
    PARAM = "param"
    COOKIE = "cookie"


class HTTPRequestData(BaseModel):
    method: str
    url: str
    headers: Dict[str, str]
    post_data: Optional[str] = None
    redirected_from_url: Optional[str] = None
    redirected_to_url: Optional[str] = None
    is_iframe: bool = False


class ResourceLocator(BaseModel):
    id: str
    request_part: RequestPart
    type_name: str