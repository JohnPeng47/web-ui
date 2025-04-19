import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field # Use field for default_factory
from typing import List, Optional, Dict, Any, Set, Tuple, Type, Iterable, Protocol, Sequence, Union
from enum import Enum
import json # Added import
import httpx # Added import
import logging
from dataclasses import replace

from playwright.sync_api import Request
from httplib import HTTPRequest, HTTPRequestData, AuthSession
from src.llm import RequestResources, Resource, ResourceType, RequestPart

log = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class ResourceLocator:
    """How to locate a particular resource id in a template request."""
    id: str
    request_part: RequestPart
    type_name: str

class NetworkError(RuntimeError):
    """Raised for transport‑level issues (DNS, TLS, timeout…)."""

class HTTPClient:
    """Thin wrapper around *one* httpx.Client for connection reuse."""

    def __init__(self, *, follow_redirects: bool = True, timeout: float = 30.0):
        self._client = httpx.Client(follow_redirects=follow_redirects, timeout=timeout)

    def shutdown(self) -> None:
        self._client.close()

    def send(
        self,
        request: HTTPRequestData,
        *,
        auth_session: Optional[AuthSession] = None,
    ) -> httpx.Response:
        # Resolve effective headers / cookies
        headers = {**request.headers}
        cookies: Dict[str, str] = {}
        if auth_session:
            # Adapt to the existing AuthSession interface
            session_cookies = getattr(auth_session, "cookies", {})
            session_headers = getattr(auth_session, "headers", {})
            headers.update(session_headers)  # auth overrides template
            cookies.update(session_cookies)

        # Decide whether to treat body as JSON
        kwargs: Dict[str, Any] = {}
        # Adapt to the existing HTTPRequestData interface which uses post_data instead of body
        post_data = getattr(request, "post_data", None)
        
        if post_data is not None:
            ctype = headers.get("content-type", "").lower()
            if "application/json" in ctype:
                try:
                    kwargs["json"] = json.loads(post_data)
                except (json.JSONDecodeError, TypeError):
                    log.warning("Could not decode JSON for %s – sending raw", request.url)
                    kwargs["content"] = post_data
            else:
                kwargs["content"] = post_data

        try:
            resp = self._client.request(
                method=request.method,
                url=request.url,
                headers=headers,
                cookies=cookies,
                **kwargs,
            )
        except httpx.RequestError as exc:
            raise NetworkError("%s %s failed: %s" % (request.method, request.url, exc)) from exc

        # Let session refresh itself
        if auth_session:
            # Adapt to the existing AuthSession interface
            update_method = getattr(auth_session, "update_session", None)
            if update_method:
                update_method(resp.headers)
            else:
                log.warning("AuthSession for user has no 'update_session' method")
        return resp

class TemplateRegistry:
    """Store the canonical request for each distinct *action* (URL)."""

    def __init__(self) -> None:
        self._templates: Dict[str, "RequestTemplate"] = {}

    def add(self, action: str, template: "RequestTemplate") -> None:
        self._templates[action] = template
        log.debug("Registered template for %s", action)

    def template(self, action: str) -> "RequestTemplate":
        return self._templates[action]

    def actions(self) -> Iterable[str]:
        return self._templates.keys()

@dataclass(slots=True)
class RequestTemplate:
    """An immutable request plus resolved ResourceLocators."""

    data: HTTPRequestData
    resource_locators: Sequence[ResourceLocator]

    def mutate_for_resource(self, *, target: str, type_name: str) -> HTTPRequestData:
        """Return a **new** HTTPRequestData with a particular id swapped in."""
        rl: Optional[ResourceLocator] = next(
            (r for r in self.resource_locators if r.type_name == type_name), None
        )
        if rl is None:
            raise ValueError(f"Template not related to {type_name}")

        new_url = self.data.url
        new_post_data = getattr(self.data, "post_data", None)
        new_headers = self.data.headers.copy()
        
        if rl.request_part == RequestPart.URL:
            new_url = new_url.replace(rl.id, target, 1)
        elif rl.request_part == RequestPart.BODY and new_post_data:
            new_post_data = new_post_data.replace(rl.id, target, 1)
        else:
            # headers unsupported for now
            raise NotImplementedError("Header replacement not implemented yet")

        # Create new data with the adapted fields
        new_data = HTTPRequestData(
            method=self.data.method,
            url=new_url,
            headers=new_headers,
            post_data=new_post_data,
            is_iframe=getattr(self.data, "is_iframe", False),
            redirected_from_url=getattr(self.data, "redirected_from_url", None),
            redirected_to_url=getattr(self.data, "redirected_to_url", None)
        )

        return new_data

class AccessGraph:
    """user  →  { resource_type → {resource_id, …} }"""

    def __init__(self) -> None:
        self._graph: Dict[str, Dict[str, Set[str]]] = {}

    # --- public API ---------------------------------------------------------
    def record(self, *, user: str, type_name: str, resource_id: str) -> None:
        self._graph.setdefault(user, {}).setdefault(type_name, set()).add(resource_id)
        log.debug("Record access: user=%s type=%s id=%s", user, type_name, resource_id)

    def other_users(self, user: str) -> Iterable[str]:
        return (u for u in self._graph.keys() if u != user)

    def resources_of_type(self, type_name: str) -> Set[str]:
        result: Set[str] = set()
        for user_map in self._graph.values():
            result |= user_map.get(type_name, set())
        return result


@dataclass(slots=True)
class PlannedTest:
    user: str
    resource_id: str
    action: str
    type_name: str


class TestPlanner:
    """Pure function object: given new observation → yield permutations to test."""

    def __init__(self, graph: AccessGraph, templates: TemplateRegistry):
        self._graph = graph
        self._templates = templates
        # Use (user, action, type_name) key for deduplication
        self._executed: Set[Tuple[str, str, str]] = set()

    # API
    def schedule_from_ingest(
        self, *, new_user: str, new_types: Sequence[Tuple[str, str]], new_action: str, is_new_user: bool
    ) -> Iterable[PlannedTest]:
        """Yield PlannedTests, deduplicated, using original 3-case logic."""

        # 1) New action → try it with existing users/resources
        for type_name, res_id in new_types:
            for user in self._graph.other_users(new_user):
                yield from self._dedup(user, res_id, new_action, type_name)

        # 2) Existing action(s) of types → try them with new resource
        for type_name, res_id in new_types:
            for action in self._actions_for_type(type_name):
                # Avoid re-testing the exact triggering request combination immediately
                if action == new_action:
                    continue
                for user in self._graph.other_users(new_user):
                    yield from self._dedup(user, res_id, action, type_name)

        # 3) New user → try them on every existing (action,resource)
        # Check if the user is genuinely new by seeing if they are in the graph *before* this ingest
        if is_new_user:
            for action in self._templates.actions():
                template = self._templates.template(action)
                for rl in template.resource_locators:
                    # Skip testing the new user on the exact action/type combo from the triggering request
                    # (This check might be redundant if action == new_action is handled, but keep for safety)
                    is_triggering_action_type = (
                        action == new_action and
                        rl.type_name in [t for t, r in new_types]
                    )
                    if is_triggering_action_type:
                        continue

                    # Test the new_user against the specific resource (rl.id) from the template
                    yield from self._dedup(new_user, rl.id, action, rl.type_name)

    # helpers

    def _actions_for_type(self, type_name: str) -> Iterable[str]:
        """Yields actions associated with a given resource type."""
        for action in self._templates.actions():
            template = self._templates.template(action)
            if any(rl.type_name == type_name for rl in template.resource_locators):
                yield action

    def _dedup(
        self, user: str, resource_id: str, action: str, type_name: str
    ) -> Iterable[PlannedTest]:
        """Deduplicates tests based on (user, action, type_name) key."""
        sig = (user, action, type_name)
        if sig not in self._executed:
            # Add signature *before* yielding
            self._executed.add(sig)
            yield PlannedTest(user, resource_id, action, type_name)

@dataclass(slots=True)
class TestResult:
    user: str
    resource_id: str
    action: str


class TestExecutor:
    """Handles mutation + HTTP send – no scheduling logic here."""

    def __init__(
        self,
        *,
        client: HTTPClient,
        templates: TemplateRegistry,
        sessions: Dict[str, AuthSession],
    ) -> None:
        self._client = client
        self._templates = templates
        self._sessions = sessions

    def execute(self, test: PlannedTest) -> TestResult:
        template = self._templates.template(test.action)
        try:
            req = template.mutate_for_resource(
                target=test.resource_id, type_name=test.type_name
            )
        except Exception as exc:
            return TestResult(
                user=test.user,
                resource_id=test.resource_id,
                action=test.action,
            )

        session = self._sessions.get(test.user)
        if session is None:
            return TestResult(
                user=test.user,
                resource_id=test.resource_id,
                action=test.action,
            )

        try:
            resp = self._client.send(req, auth_session=session)
        except NetworkError as exc:
            return TestResult(
                user=test.user,
                resource_id=test.resource_id,
                action=test.action,
            )
        except Exception as exc:
            # Catch other exceptions that might happen
            return TestResult(
                user=test.user,
                resource_id=test.resource_id,
                action=test.action,
            )

        return TestResult(
            user=test.user,
            resource_id=test.resource_id,
            action=test.action,
        )

class AuthzTester:
    """High level orchestrator: ingest traffic then automatically test perms."""

    def __init__(self, http_client: Optional[HTTPClient] = None):
        self._client = http_client or HTTPClient()
        self._graph = AccessGraph()
        self._templates = TemplateRegistry()
        self._sessions: Dict[str, AuthSession] = {}
        self._planner = TestPlanner(self._graph, self._templates)
        self._executor = TestExecutor(
            client=self._client, templates=self._templates, sessions=self._sessions
        )
        self.findings: List[Union[TestResult, str]] = []

    # Convert from IntruderRequest to ResourceLocator
    def _convert_resource_to_locator(self, resource: Resource) -> Optional[ResourceLocator]:
        if not resource.id or not resource.type or not hasattr(resource.type, "name"):
            return None
            
        # Convert the imported RequestPart to our local RequestPart
        resource_part = resource.request_part
        # Use direct enum comparison instead of string conversion
        if resource_part == RequestPart.URL:
            local_part = RequestPart.URL
        elif resource_part == RequestPart.BODY:
            local_part = RequestPart.BODY
        elif resource_part == RequestPart.HEADERS:
            local_part = RequestPart.HEADERS
        else:
            log.warning("Unknown RequestPart type: %s", resource_part)
            return None
        
        return ResourceLocator(
            id=resource.id,
            request_part=local_part,
            type_name=resource.type.name
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    
    # Add a compatibility method to maintain existing interface
    def ingest_request(self, request: "IntruderRequest") -> None:
        """Legacy method to ingest IntruderRequest objects."""
        user_id = request.user_id
        if not user_id:
            log.warning("Request %s lacks user_id. Skipping.", request.url)
            return
            
        # Extract resource locators from request
        resource_locators: List[ResourceLocator] = []
        auth_info = request.attack_info.get("AUTH")
        if auth_info and auth_info.resources:
            for res in auth_info.resources:
                locator = self._convert_resource_to_locator(res)
                if locator:
                    resource_locators.append(locator)
                    
        if not resource_locators:
            log.warning("Request %s lacks resource information. Skipping.", request.url)
            return
            
        # Get session if available
        session = getattr(request, "_auth_session", None)
        
        # Use the new-style ingest with the extracted information
        self.ingest(
            user=user_id,
            request=request._data,  # Access the underlying HTTPRequestData
            resource_locators=resource_locators,
            session=session
        )

    def ingest(
        self,
        *,
        user: str,
        request: HTTPRequestData,
        resource_locators: Sequence[ResourceLocator],
        session: Optional[AuthSession] = None,
    ) -> None:
        """Feed a single *observed* request into the system."""
        action = request.url  # naive – could be method+url later

        # Check if user is new *before* recording them in the graph
        is_truly_new_user = user not in self._graph._graph

        # Persist structures
        self._templates.add(action, RequestTemplate(request, resource_locators))
        if session:
            self._sessions[user] = session
        for rl in resource_locators:
            self._graph.record(user=user, type_name=rl.type_name, resource_id=rl.id)

        # Plan tests
        new_types = [(rl.type_name, rl.id) for rl in resource_locators]
        for test in self._planner.schedule_from_ingest(
            new_user=user, new_types=new_types, new_action=action, is_new_user=is_truly_new_user
        ):
            res = self._executor.execute(test)
            self.findings.append(res)

    # Convenience helper – call at shutdown
    def close(self) -> None:
        self._client.shutdown()


# ---------------------------------------------------------------------------
# Compatibility with IntruderRequest
# ---------------------------------------------------------------------------

# Keep IntruderRequest class from the original file for compatibility
# This class definition should remain as is from the original file

class IntruderRequest(HTTPRequest):
    def __init__(self,
                 data: HTTPRequestData,
                 user_id: Optional[str] = None,
                 auth_info: Optional[RequestResources] = None) -> None:
        """Represents an HTTP request for the Intruder tool."""
        super().__init__(data)

        self.user_id = user_id
        self.attack_info = {
            "AUTH": auth_info, # Store under attack_info
        }
        # Store the AuthSession directly if possible, might need adjustment
        self._auth_session: Optional[AuthSession] = AuthSession(data.headers) if data.headers else None # Basic session from headers

    @classmethod
    def from_json(cls,
                  data: Dict[str, Any],
                  user_id: Optional[str] = None,
                  auth_info: Optional[RequestResources] = None) -> "IntruderRequest":
        http_request = super().from_json(data)
        return cls(http_request._data, user_id, auth_info)

    @classmethod
    def from_pw(
        cls,
        request: Request,
        user_id: Optional[str] = None,
        auth_info: Optional[RequestResources] = None
    ) -> "IntruderRequest":
        http_request = super().from_pw(request)
        return cls(http_request._data, user_id, auth_info)


# ---------------------------------------------------------------------------
# __all__ for * import hygiene
# ---------------------------------------------------------------------------

__all__ = [
    "AuthzTester",
    "HTTPRequestData",
    "ResourceLocator",
    "RequestPart",
    "HTTPClient",
    "NetworkError",
    "TestResult",
    "IntruderRequest",  # Keep for backward compatibility
]