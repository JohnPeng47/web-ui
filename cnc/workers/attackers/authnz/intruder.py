from dataclasses import dataclass, field, replace  # Use field for default_factory
from typing import List, Optional, Dict, Any, Set, Tuple, Type, Iterable, Protocol, Sequence, Union
from enum import Enum
import json  # Added import
import httpx  # Added import
import logging
from abc import ABC, abstractmethod

from playwright.sync_api import Request
from httplib import HTTPRequest, HTTPRequestData, AuthSession, ResourceLocator
from src.llm import RequestResources, Resource, ResourceType, RequestPart

from cnc.services.attack import FindingsStore
from .models import (
    AuthNZAttack,
    PlannedTest,
    HorizontalUserAuthz,
    VerticalUserAuthz,
    HorizontalResourceAuthz,
    VerticalResourceAuthz,
)

log = logging.getLogger(__name__)


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
        post_data = getattr(request, "post_data", None)

        if post_data is not None:
            ctype = headers.get("content-type", "").lower()
            if "application/json" in ctype:
                # Check if post_data is already a dict/JSON object or a string
                if isinstance(post_data, dict):
                    kwargs["json"] = post_data
                else:
                    try:
                        kwargs["json"] = json.loads(post_data)
                    except (json.JSONDecodeError, TypeError):
                        log.warning("Could not decode JSON for %s – sending raw", request.url)
                        log.warning("Sending raw data: %s", post_data)
                        kwargs["content"] = post_data.encode("utf-8") if isinstance(post_data, str) else post_data
            else:
                if isinstance(post_data, str):
                    kwargs["content"] = post_data.encode("utf-8")
                else:
                    kwargs["content"] = post_data

        # ── TRACE: outbound request ────────────────────────────
        log.info(f"[SEND ] {request.method} {request.url}")
        # ───────────────────────────────────────────────────────

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

        # ── TRACE: response line ───────────────────────────────
        log.info(f"[SEND ] ← {resp.status_code} ({len(resp.content)} bytes)")
        # ───────────────────────────────────────────────────────

        # Let session refresh itself
        if auth_session:
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
    """Frozen request + its ResourceLocators."""

    data: HTTPRequestData
    resource_locators: Sequence[ResourceLocator]

    def get_resource_types(self) -> Set[str]:
        return {rl.type_name for rl in self.resource_locators}

    def mutate_for_resource(
        self, *, target: str | None, type_name: str | None
    ) -> HTTPRequestData:
        """
        Return a **new** HTTPRequestData with a selected locator value swapped.
        If either `target` or `type_name` is None, return the request untouched.
        """
        if not target or not type_name:
            return HTTPRequestData(
                method=self.data.method,
                url=self.data.url,
                headers=self.data.headers.copy(),
                post_data=getattr(self.data, "post_data", None),
                is_iframe=getattr(self.data, "is_iframe", False),
                redirected_from_url=getattr(self.data, "redirected_from_url", None),
                redirected_to_url=getattr(self.data, "redirected_to_url", None),
            )

        rl = next((r for r in self.resource_locators if r.type_name == type_name), None)
        if rl is None:
            raise ValueError(f"{type_name=} absent from template")

        new_url = self.data.url
        new_post_data = getattr(self.data, "post_data", None)
        if rl.request_part == RequestPart.URL:
            new_url = new_url.replace(rl.id, target, 1)
        elif rl.request_part == RequestPart.BODY and new_post_data:
            # Handle both string and JSON formats
            if isinstance(new_post_data, str):
                new_post_data = new_post_data.replace(rl.id, target, 1)
            elif isinstance(new_post_data, dict):
                post_data_str = json.dumps(new_post_data)
                post_data_str = post_data_str.replace(rl.id, target, 1)
                new_post_data = json.loads(post_data_str)

        return HTTPRequestData(
            method=self.data.method,
            url=new_url,
            headers=self.data.headers.copy(),
            post_data=new_post_data,
            is_iframe=getattr(self.data, "is_iframe", False),
            redirected_from_url=getattr(self.data, "redirected_from_url", None),
            redirected_to_url=getattr(self.data, "redirected_to_url", None),
        )


class AccessGraph:
    """
    user  →  { resource_type → {resource_id, …} }
    PLUS: (resource_type, resource_id) → set(role)
    """

    def __init__(self) -> None:
        self._graph: dict[str, dict[str, set[str]]] = {}
        self._resource_roles: dict[tuple[str, str], set[str]] = {}

    # ── public API ────────────────────────────────────────────────────────
    def record(
        self, *, user: str, role: str, type_name: str, resource_id: str
    ) -> None:
        self._graph.setdefault(user, {}).setdefault(type_name, set()).add(resource_id)
        self._resource_roles.setdefault((type_name, resource_id), set()).add(role)
        log.debug(
            "Record access: user=%s role=%s type=%s id=%s",
            user,
            role,
            type_name,
            resource_id,
        )

    def other_users(self, user: str) -> Iterable[str]:
        return (u for u in self._graph.keys() if u != user)

    def resources_of_type(self, type_name: str) -> set[str]:
        out: set[str] = set()
        for per_user in self._graph.values():
            out |= per_user.get(type_name, set())
        return out

    def roles_of_resource(self, *, type_name: str, resource_id: str) -> set[str]:
        """Return every role that has touched (type,id) so far."""
        return self._resource_roles.get((type_name, resource_id), set())


class TestPlanner:
    """
    Given one newly‑observed request, yield **AuthNZAttack** instances that
    exercise all user / role / resource permutations (static only).
    """

    def __init__(self, graph: AccessGraph, templates: TemplateRegistry):
        self._graph = graph
        self._templates = templates
        self._executed: set[tuple[str, str, str, str]] = set()
        # (variant, user, action, type_name)

    # ── helpers ----------------------------------------------------------
    @staticmethod
    def _split_role(u: str) -> tuple[str, str]:
        """
        Expect usernames of form  "alice:admin".
        Returns  (user_id, role)
        """
        if ":" in u:
            parts = u.split(":", 1)
            return (parts[0], parts[1])
        return (u, "")  # empty role if not encoded

    def _actions_for_type(self, type_name: str) -> Iterable[str]:
        """Yields actions associated with a given resource type."""
        for action in self._templates.actions():
            template = self._templates.template(action)
            if any(rl.type_name == type_name for rl in template.resource_locators):
                yield action

    def _dedup(
        self,
        variant: type[AuthNZAttack],
        *,
        user: str,
        resource_id: str | None,
        action: str,
        type_name: str | None,
    ) -> Iterable[AuthNZAttack]:
        sig = (variant.__name__, user, action, type_name or "")
        if sig in self._executed:
            return
        self._executed.add(sig)

        # ── TRACE: attack scheduled ────────────────────────────
        log.info(
            f"[PLAN ] {variant.__name__:<22} → user={user} "
            f"action={action} type={type_name or '-'} id={resource_id or '-'}"
        )
        # ───────────────────────────────────────────────────────

        yield variant(
            attack_info=PlannedTest(
                user=user, resource_id=resource_id, action=action, type_name=type_name
            )
        )

    # ── public API -------------------------------------------------------
    def schedule_from_ingest(
        self,
        *,
        new_username: str,
        new_role: str,
        new_resources: Sequence[tuple[str, str]],
        new_action: str,
        is_new_user: bool,
    ) -> Iterable[AuthNZAttack]:
        combined_new_user = f"{new_username}:{new_role}"

        new_types = [r[0] for r in new_resources]
        new_rids = [r[1] for r in new_resources]

        # 1) New action  →  try it with existing users (no ID swap)
        for u in self._graph.other_users(combined_new_user):
            _, other_role = self._split_role(u)
            variant = HorizontalUserAuthz if other_role == new_role else VerticalUserAuthz
            
            log.info(f"[FINDING-1 | UserSub]: {(variant.__name__, u, None, new_action, None)}")

            yield from self._dedup(
                variant, user=u, resource_id=None, action=new_action, type_name=None
            )

        # 2) Same action(s) → try them with new *resource* for all other users
        for type_name, res_id in new_resources:
            for action in self._actions_for_type(type_name):
                if action == new_action:
                    continue
                for u in self._graph.other_users(combined_new_user):
                    _, other_role = self._split_role(u)
                    variant = (
                        HorizontalUserAuthz if other_role == new_role else VerticalUserAuthz
                    )

                    log.info(f"[FINDING-2 | ResourceSub]: {(variant.__name__, u, res_id, action, type_name)}")

                    yield from self._dedup(
                        variant,
                        user=u,
                        resource_id=res_id,
                        action=action,
                        type_name=type_name,
                    )

        # 3) New user  → try them on every known (action, type, id)
        if is_new_user:
            for action in self._templates.actions():
                tpl = self._templates.template(action)
                for type_name in tpl.get_resource_types():
                    for rid in self._graph.resources_of_type(type_name):
                        if rid in new_rids:
                            continue

                        prior_roles = self._graph.roles_of_resource(
                            type_name=type_name, resource_id=rid
                        )

                        log.info(f"[FINDING-3 | NewUserSub]: {(variant.__name__, combined_new_user, rid, action, type_name)}")

                        variant = (
                            HorizontalResourceAuthz
                            if new_role in prior_roles
                            else VerticalResourceAuthz
                        )
                        yield from self._dedup(
                            variant,
                            user=combined_new_user,
                            resource_id=rid,
                            action=action,
                            type_name=type_name,
                        )


class TestExecutor:
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

    def execute(self, attack: AuthNZAttack) -> AuthNZAttack:
        attack_info = attack.attack_info
        template = self._templates.template(attack_info.action)
        req = template.mutate_for_resource(
            target=attack_info.resource_id, type_name=attack_info.type_name
        )
        sess = self._sessions.get(attack_info.user)
        if not sess:
            return attack

        self._client.send(req, auth_session=sess)
        return attack


class AuthzTester:
    """
    Attack module that is used to brute-force all *static* authorization permutations of:
    (user, role) x (verb, url) x (resource_id, resource_type)
    """
    def __init__(
        self,
        http_client: Optional[HTTPClient] = None,
        findings_log: Optional[FindingsStore] = None,
    ) -> None:
        self._client = http_client or HTTPClient()
        self._graph = AccessGraph()
        self._templates = TemplateRegistry()
        self._sessions: Dict[str, AuthSession] = {}
        self._planner = TestPlanner(self._graph, self._templates)
        self._executor = TestExecutor(
            client=self._client, templates=self._templates, sessions=self._sessions
        )
        self._findings_log = findings_log
        self.findings: List[Union[AuthNZAttack, str]] = []

    # Convert from IntruderRequest to ResourceLocator
    def _convert_resource_to_locator(self, resource: Resource) -> Optional[ResourceLocator]:
        if not resource.id or not resource.type or not hasattr(resource.type, "name"):
            return None

        resource_part = resource.request_part
        if resource_part == RequestPart.URL:
            local_part = RequestPart.URL
        elif resource_part == RequestPart.BODY:
            local_part = RequestPart.BODY
        elif resource_part == RequestPart.HEADERS:
            local_part = RequestPart.HEADERS
        else:
            log.warning("Unknown RequestPart type: %s", resource_part)
            return None

        return ResourceLocator(id=resource.id, request_part=local_part, type_name=resource.type.name)

    def ingest(
        self,
        *,
        username: str,
        role: str,
        request: HTTPRequestData,
        resource_locators: Sequence[ResourceLocator],
        session: AuthSession | None = None,
    ) -> None:
        """
        Observe one live request and enqueue all static‑AuthZ permutations.
        """
        # ── TRACE: live request observed ───────────────────────
        log.info(f"[INGEST] {request.method} {request.url}  user={username}  role={role}")
        # ───────────────────────────────────────────────────────

        action_key = f"{request.method.upper()} {request.url}"
        combined_user = f"{username}:{role}"

        is_new_user = combined_user not in self._graph._graph

        self._templates.add(action_key, RequestTemplate(request, resource_locators))
        if session:
            self._sessions[combined_user] = session
        for rl in resource_locators:
            self._graph.record(
                user=combined_user,
                role=role,
                type_name=rl.type_name,
                resource_id=rl.id,
            )

        new_types = [(rl.type_name, rl.id) for rl in resource_locators]
        new_resources_for_planning: Sequence[tuple[str, str]] = (
            new_types if new_types else [("", "")]
        )
        for attack in self._planner.schedule_from_ingest(
            new_username=username,
            new_role=role,
            new_resources=new_resources_for_planning,
            new_action=action_key,
            is_new_user=is_new_user,
        ):
            attack_result = self._executor.execute(attack)
            self.findings.append(attack_result)
            if self._findings_log:
                self._findings_log.append(attack_result)
            log.info("AuthZ‑finding: %s", attack_result)

    # Convenience helper – call at shutdown
    def close(self) -> None:
        self._client.shutdown()

    def get_findings(self):
        return self.findings


__all__ = [
    "AuthzTester",
    "HTTPRequestData",
    "ResourceLocator",
    "RequestPart",
    "HTTPClient",
    "NetworkError",
    "AuthNZAttack",
    "IntruderRequest",  # Keep for backward compatibility
]
