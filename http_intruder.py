from httplib import HTTPRequest, HTTPRequestData
from playwright.sync_api import Request

from src.llm import RequestAuthInfo
from typing import Any, Dict, List, Optional

class IntruderRequest(HTTPRequest):
    def __init__(self, 
                 data: HTTPRequestData, 
                 user_id: Optional[str] = None,
                 auth_info: Optional[RequestAuthInfo] = None) -> None:
        """Represents an HTTP request for the Intruder tool."""
        super().__init__(data)

        self.user_id = user_id
        self.attack_info = {
            "AUTH": auth_info,
        }

    @classmethod
    def from_json(cls, 
                  data: Dict[str, Any], 
                  user_id: Optional[str] = None,
                  auth_info: Optional[RequestAuthInfo] = None) -> "IntruderRequest":
        http_request = super().from_json(data)
        return cls(http_request._data, user_id, auth_info)
    
    @classmethod
    def from_pw(
        cls, 
        request: Request, 
        user_id: Optional[str] = None,
        auth_info: Optional[RequestAuthInfo] = None
    ) -> "IntruderRequest":
        http_request = super().from_pw(request)
        return cls(http_request._data, user_id, auth_info)        
    
    