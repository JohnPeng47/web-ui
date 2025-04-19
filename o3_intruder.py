from __future__ import annotations
"""Intruder – Refactored core
=================================
This single‑file refactor demonstrates the *shape* and guiding principles we
outlined in the review:
    • clear layering (domain vs infrastructure)
    • typed public APIs (mypy‑clean)
    • no print() – structured logging instead
    • single‑responsibility classes kept <150 LOC
Feel free to split it into multiple modules later (models.py, http.py …).  This
layout compiles and can be integration‑tested as‑is so you can migrate
incrementally.
"""

import json
import logging
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Set, Tuple

import httpx

# ---------------------------------------------------------------------------
# Logging setup – the CLI or host app should wire handlers & levels.
# ---------------------------------------------------------------------------
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain models (pure, no side‑effects) – Could live in models.py
# ---------------------------------------------------------------------------


class RequestPart(str, Enum):
    """Where in the HTTP request a resource id lives."""

    URL = "url"
    BODY = "body"
    HEADERS = "headers"


@dataclass(frozen=True, slots=True)
class ResourceLocator:
    """How to locate a particular resource id in a template request."""

    id: str
    request_part: RequestPart
    type_name: str


# ---------------------------------------------------------------------------
# Auth session abstraction
# ---------------------------------------------------------------------------


class AuthSession(Protocol):
    """Anything that can provide cookies / headers and be refreshed."""

    @property
    def cookies(self) -> Dict[str, str]: ...

    @property
    def headers(self) -> Dict[str, str]: ...

    def update_from_response(self, resp: httpx.Response) -> None: ...


# ---------------------------------------------------------------------------
# HTTP layer – infrastructure
# ---------------------------------------------------------------------------


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
        request: "HTTPRequestData",
        *,
        auth_session: Optional[AuthSession] = None,
    ) -> httpx.Response:
        # Resolve effective headers / cookies
        headers = {**request.headers}
        cookies: Dict[str, str] = {}
        if auth_session:
            headers |= auth_session.headers  # auth overrides template
            cookies |= auth_session.cookies

        # Decide whether to treat body as JSON
        kwargs: Dict[str, Any] = {}
        if request.body is not None:
            ctype = headers.get("content-type", "").lower()
            if "application/json" in ctype:
                try:
                    kwargs["json"] = json.loads(request.body)
                except (json.JSONDecodeError, TypeError):
                    log.warning("Could not decode JSON for %s – sending raw", request.url)
                    kwargs["content"] = request.body
            else:
                kwargs["content"] = request.body

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
            auth_session.update_from_response(resp)
        return resp


# ---------------------------------------------------------------------------
# Low‑level HTTP request description (immutable) – could be in models.py
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HTTPRequestData:
    method: str
    url: str
    headers: Dict[str, str]
    body: Optional[str] = None
    # The four fields below are kept because the original heir had them; ignored here
    is_iframe: bool = False
    redirected_from_url: Optional[str] = None
    redirected_to_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Template registry (action → request)  --------------------------------------
# ---------------------------------------------------------------------------


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

        new_data = self.data
        if rl.request_part is RequestPart.URL:
            new_data = replace(new_data, url=new_data.url.replace(rl.id, target, 1))
        elif rl.request_part is RequestPart.BODY and new_data.body:
            new_data = replace(new_data, body=new_data.body.replace(rl.id, target, 1))
        else:
            # headers unsupported for now
            raise NotImplementedError("Header replacement not implemented yet")

        return new_data


# ---------------------------------------------------------------------------
# Access graph – who touched what; pure data store
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Planner – decide which tests to run
# ---------------------------------------------------------------------------


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
        self._executed: Set[Tuple[str, str, str]] = set()  # (user,id,action)

    # API

    def schedule_from_ingest(
        self, *, new_user: str, new_types: Sequence[Tuple[str, str]], new_action: str
    ) -> Iterable[PlannedTest]:
        """Yield PlannedTests, deduplicated."""

        # 1) New action → try it with existing users/resources
        for type_name, res_id in new_types:
            for user in self._graph.other_users(new_user):
                yield from self._dedup(user, res_id, new_action, type_name)

        # 2) Existing action(s) of types → try them with new resource
        for type_name, res_id in new_types:
            for action in self._actions_for_type(type_name):
                for user in self._graph.other_users(new_user):
                    yield from self._dedup(user, res_id, action, type_name)

        # 3) New user → try them on every existing (action,resource)
        for action in self._templates.actions():
            template = self._templates.template(action)
            for rl in template.resource_locators:
                for res_id in self._graph.resources_of_type(rl.type_name):
                    yield from self._dedup(new_user, res_id, action, rl.type_name)

    # helpers

    def _actions_for_type(self, type_name: str) -> Iterable[str]:
        for action in self._templates.actions():
            template = self._templates.template(action)
            if any(rl.type_name == type_name for rl in template.resource_locators):
                yield action

    def _dedup(
        self, user: str, resource_id: str, action: str, type_name: str
    ) -> Iterable[PlannedTest]:
        sig = (user, resource_id, action)
        if sig not in self._executed:
            self._executed.add(sig)
            yield PlannedTest(user, resource_id, action, type_name)


# ---------------------------------------------------------------------------
# Executor – mutate, send, analyse, emit structured result
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TestResult:
    user: str
    resource_id: str
    action: str
    status: int
    note: str


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
                status=-1,
                note=f"mutation-error: {exc}",
            )

        session = self._sessions.get(test.user)
        if session is None:
            return TestResult(
                user=test.user,
                resource_id=test.resource_id,
                action=test.action,
                status=-1,
                note="no-session",
            )

        try:
            resp = self._client.send(req, auth_session=session)
        except NetworkError as exc:
            return TestResult(
                user=test.user,
                resource_id=test.resource_id,
                action=test.action,
                status=-1,
                note=str(exc),
            )

        note = "ALLOWED" if 200 <= resp.status_code < 300 else "DENIED" if resp.status_code in (401, 403) else "OTHER"
        return TestResult(
            user=test.user,
            resource_id=test.resource_id,
            action=test.action,
            status=resp.status_code,
            note=note,
        )


# ---------------------------------------------------------------------------
# Ingest façade – what callers use (combines all sub‑objects)
# ---------------------------------------------------------------------------


class AuthzTester:
    """High‑level orchestrator: ingest traffic then automatically test perms."""

    def __init__(self, client: Optional[HTTPClient] = None):
        self._client = client or HTTPClient()
        self._graph = AccessGraph()
        self._templates = TemplateRegistry()
        self._sessions: Dict[str, AuthSession] = {}
        self._planner = TestPlanner(self._graph, self._templates)
        self._executor = TestExecutor(
            client=self._client, templates=self._templates, sessions=self._sessions
        )
        self.findings: List[TestResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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

        # Persist structures
        self._templates.add(action, RequestTemplate(request, resource_locators))
        if session:
            self._sessions[user] = session
        for rl in resource_locators:
            self._graph.record(user=user, type_name=rl.type_name, resource_id=rl.id)

        # Plan tests
        new_types = [(rl.type_name, rl.id) for rl in resource_locators]
        for test in self._planner.schedule_from_ingest(
            new_user=user, new_types=new_types, new_action=action
        ):
            res = self._executor.execute(test)
            if res.note == "ALLOWED":
                log.warning("Potential bypass! %s", res)
            self.findings.append(res)

    # Convenience helper – call at shutdown
    def close(self) -> None:
        self._client.shutdown()


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
]
