from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set, List, Tuple
import re
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from schemas.http import HTTPRequestData, EnrichedRequest
from services.queue import queues
from database.models import AuthSession


class BaseAttackWorker(ABC):
    def __init__(self, queue_id: str, db_session: AsyncSession):
        self.queue_id = queue_id
        self.db = db_session
    
    @abstractmethod
    async def run(self):
        pass
    
    @abstractmethod
    async def ingest(
        self,
        request: HTTPRequestData,
        username: Optional[str] = None,
        role: Optional[str] = None,
        session: Optional[AuthSession] = None,
    ):
        pass
    
    def _explode(self, enriched: EnrichedRequest) -> Dict[str, Any]:
        """Convert EnrichedRequest into kwargs for ingest method."""
        return {
            "request": enriched.request,
            "username": enriched.username,
            "role": enriched.role,
            # Session would be fetched separately if needed
            "session": None
        }


class AuthzAttacker(BaseAttackWorker):
    """
    Worker that analyzes requests for authorization vulnerabilities.
    
    It detects:
    1. URL patterns that suggest resource access that might be protected
    2. Differences between requests from different roles
    3. Sequential access patterns that might indicate IDOR vulnerabilities
    """
    
    def __init__(self, queue_id: str = "enriched_requests_authz", db_session: AsyncSession = None):
        super().__init__(queue_id, db_session)
        # Track URLs accessed by each role
        self.role_access_map: Dict[str, Set[str]] = {}
        # Track sequential ID access patterns
        self.sequential_accesses: Dict[str, List[Tuple[str, str]]] = {}  # pattern -> [(user, resource_id)]
        # Common sensitive endpoints
        self.sensitive_patterns = [
            r"/admin", r"/settings", r"/profile",
            r"/users/\d+", r"/api/v\d/users/\d+",
            r"/accounts/\d+", r"/orders/\d+",
            r"/documents/\d+", r"/files/\d+"
        ]
    
    async def run(self):
        sub_q = queues.get(self.queue_id).subscribe()
        while True:
            enr: EnrichedRequest = await sub_q.get()
            await self.ingest(**self._explode(enr))
    
    async def ingest(
        self,
        request: HTTPRequestData,
        username: Optional[str] = None,
        role: Optional[str] = None,
        session: Optional[AuthSession] = None,
    ):
        """Process a request for authorization vulnerabilities."""
        if not username:
            return  # Skip unauthenticated requests
        
        url = str(request.url)
        
        # Track access by role
        role_key = role or "unknown_role"
        if role_key not in self.role_access_map:
            self.role_access_map[role_key] = set()
        self.role_access_map[role_key].add(url)
        
        # Check for sensitive endpoint access
        for pattern in self.sensitive_patterns:
            if re.search(pattern, url):
                self._record_sensitive_access(username, role_key, pattern, url)
                break
        
        # Check for sequential ID patterns (IDOR)
        self._analyze_for_idor(username, url)
    
    def _record_sensitive_access(self, username: str, role: str, pattern: str, url: str):
        """Record access to sensitive endpoints for later analysis."""
        # This would typically persist or alert on sensitive access patterns
        # For simplicity, this example just logs (in a real system would alert/store)
        print(f"Sensitive access: {username} ({role}) accessed {pattern} at {url}")
    
    def _analyze_for_idor(self, username: str, url: str):
        """Analyze URL for Insecure Direct Object Reference patterns."""
        # Look for numeric IDs in URLs - potential IDOR targets
        id_patterns = [
            (r"/users/(\d+)", "user_id"),
            (r"/orders/(\d+)", "order_id"),
            (r"/accounts/(\d+)", "account_id"),
            (r"/documents/(\d+)", "document_id"),
            (r"/api/v\d/(\w+)/(\d+)", "api_resource")
        ]
        
        for pattern, resource_type in id_patterns:
            match = re.search(pattern, url)
            if match:
                resource_id = match.group(1)  # Extract the ID
                
                # Record this access
                if resource_type not in self.sequential_accesses:
                    self.sequential_accesses[resource_type] = []
                
                self.sequential_accesses[resource_type].append((username, resource_id))
                
                # Check for suspicious patterns - like sequential access
                self._check_sequential_access(resource_type, username)
    
    def _check_sequential_access(self, resource_type: str, username: str):
        """Check if a user is accessing resources in sequential order (potential IDOR)."""
        # Only check if we have enough data points
        if resource_type not in self.sequential_accesses or len(self.sequential_accesses[resource_type]) < 3:
            return
        
        # Get this user's access history for this resource type
        user_accesses = [
            int(res_id) for user, res_id in self.sequential_accesses[resource_type]
            if user == username and res_id.isdigit()  # Ensure the resource ID is numeric
        ]
        
        # Sort accesses to check for sequential patterns
        user_accesses.sort()
        
        # Check for at least 3 sequential IDs
        for i in range(len(user_accesses) - 2):
            if user_accesses[i] + 1 == user_accesses[i+1] and user_accesses[i+1] + 1 == user_accesses[i+2]:
                # Found a sequence of 3 consecutive IDs - potential IDOR vulnerability
                print(f"Potential IDOR: {username} accessed {resource_type} with sequential IDs: {user_accesses[i]}, {user_accesses[i+1]}, {user_accesses[i+2]}")
                break