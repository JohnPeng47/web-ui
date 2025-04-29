from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import re
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.http import HTTPMessage, EnrichedRequest
from services.queue import queues
from database import crud
from database.models import AuthSession


class BaseRequestEnrichmentWorker(ABC):
    def __init__(self, *, sub_queue_id: str, pub_queue_id: str):
        self.sub_id = sub_queue_id
        self.pub_id = pub_queue_id
    
    @abstractmethod
    async def run(self):
        pass
    
    @abstractmethod
    async def _enrich(self, message: HTTPMessage) -> EnrichedRequest:
        pass


class SimpleEnrichmentWorker(BaseRequestEnrichmentWorker):
    def __init__(self, *, sub_queue_id: str, pub_queue_id: str, db_session: AsyncSession):
        super().__init__(sub_queue_id=sub_queue_id, pub_queue_id=pub_queue_id)
        self.db = db_session
    
    async def run(self):
        sub_q = queues.get(self.sub_id).subscribe()
        pub_ch = queues.get(self.pub_id)
        
        while True:
            msg: HTTPMessage = await sub_q.get()
            enr = await self._enrich(msg)
            await pub_ch.publish(enr)
    
    async def _enrich(self, message: HTTPMessage) -> EnrichedRequest:
        """
        Enriches an HTTP message by extracting authentication/session information.
        
        This implementation looks for:
        1. Session cookies (common session identifiers)
        2. Authorization headers (Bearer tokens, Basic auth)
        3. Form-based auth in POST data (username/password fields)
        """
        request = message.request
        enriched = EnrichedRequest(request=request)
        
        # Extract session information from cookies
        session_id = self._extract_session_id(request.headers)
        if session_id:
            enriched.session_id = session_id
            
            # Try to find session in database
            app_id = self._extract_app_id_from_url(str(request.url))
            if app_id:
                session = await crud.get_session_by_id(self.db, app_id, session_id)
                if session:
                    enriched.username = session.username
                    enriched.role = session.role
        
        # Look for username/role in Authorization header
        if "Authorization" in request.headers:
            auth_data = self._extract_from_auth_header(request.headers["Authorization"])
            if auth_data and "username" in auth_data:
                enriched.username = auth_data["username"]
                enriched.role = auth_data.get("role", "user")  # Default to 'user' role
        
        # Check for login form submission
        if request.method == "POST" and request.post_data:
            auth_data = self._extract_from_form_data(request.post_data)
            if auth_data and "username" in auth_data:
                enriched.username = auth_data["username"]
                enriched.role = auth_data.get("role", "user")
        
        return enriched
    
    def _extract_session_id(self, headers: Dict[str, str]) -> Optional[str]:
        """Extract session ID from cookies or other headers."""
        # Check for cookies header
        if "Cookie" in headers:
            cookies = headers["Cookie"]
            # Common session cookie names
            for session_key in ["sessionid", "session", "JSESSIONID", "sid", "PHPSESSID"]:
                match = re.search(f"{session_key}=([^;]+)", cookies)
                if match:
                    return match.group(1)
        
        # Check for custom session headers
        for header, value in headers.items():
            if "session" in header.lower():
                return value
        
        return None
    
    def _extract_from_auth_header(self, auth_header: str) -> Optional[Dict[str, Any]]:
        """Extract authentication data from Authorization header."""
        # Basic auth
        if auth_header.startswith("Basic "):
            import base64
            try:
                decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                if ':' in decoded:
                    username, password = decoded.split(':', 1)
                    return {"username": username}
            except Exception:
                pass
        
        # Bearer token - would need further JWT parsing for actual extraction
        if auth_header.startswith("Bearer "):
            # Simple extraction for demo - in real app would parse JWT
            return {"username": "token_user", "role": "token_role"}
            
        return None
    
    def _extract_from_form_data(self, post_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract username and role from POST form data."""
        result = {}
        
        # Common username field names
        for user_field in ["username", "user", "email", "login"]:
            if user_field in post_data:
                result["username"] = post_data[user_field]
                break
        
        # Look for role information
        for role_field in ["role", "group", "permission"]:
            if role_field in post_data:
                result["role"] = post_data[role_field]
                break
        
        return result if "username" in result else None
    
    def _extract_app_id_from_url(self, url: str) -> Optional[str]:
        """Extract application ID from URL if present."""
        # This is a simplified example - real implementation would depend on URL structure
        match = re.search(r"/application/([0-9a-f-]+)/", url)
        if match:
            return match.group(1)
        return None