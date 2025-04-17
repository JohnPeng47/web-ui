import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field # Use field for default_factory
from typing import List, Optional, Dict, Any, Set, Tuple, Type
from enum import Enum
import json # Added import
import httpx # Added import

from playwright.sync_api import Request
from httplib import HTTPRequest, HTTPRequestData, AuthSession
from src.llm import RequestResources, RequestPart, Resource, ResourceType # Added Resource, ResourceType

# --- HTTPClient Wrapper ---
class HTTPClient:
    """A wrapper around httpx.Client for sending HTTP requests."""
    def __init__(self, follow_redirects: bool = True, timeout: float = 30.0):
        self._follow_redirects = follow_redirects
        self._timeout = timeout

    def send(self, request: "IntruderRequest", # Changed from self to request
             auth_session: Optional[AuthSession] = None,
             update_session_from_response: bool = True) -> Optional[httpx.Response]:
        """Sends the HTTP request using httpx."""
        session_to_use = auth_session

        if not session_to_use:
            # If no specific session, maybe fall back to request's inherent auth if any?
            # For now, proceed without session-specific cookies/headers.
            print(f"Warning: Sending request {request.url} without a specific AuthSession.")
            session_cookies = {}
            session_headers = {}
        else:
            # Assuming AuthSession has methods/properties like these based on linter errors
            session_cookies = getattr(session_to_use, 'cookies', {}) # Use getattr for safety
            session_headers = getattr(session_to_use, 'headers', {}) # Use getattr for safety


        # Start with request's headers (assuming lowercase property)
        final_headers = request.headers.copy() # Make a copy
        final_headers.update(session_headers) # Session headers override request's
        final_headers.pop('cookie', None) # Remove if passing via cookies param explicitly

        request_params = {}
        content_type = final_headers.get('content-type', '').lower()
        post_data = request.post_data # Access post_data from request object
        if post_data is not None:
             # Basic logic for content/json based on content-type
             if 'application/json' in content_type:
                 try:
                     request_params['json'] = json.loads(post_data)
                 except (json.JSONDecodeError, TypeError):
                     print(f"Warning: Failed to decode JSON body for {request.url}, sending as raw content.")
                     request_params['content'] = post_data
             else:
                 request_params['content'] = post_data

        try:
            # Use a new client instance for each request to ensure isolation
            # unless specific session persistence across calls is needed via httpx.Client directly.
            with httpx.Client(follow_redirects=self._follow_redirects, timeout=self._timeout,
                              cookies=session_cookies) as client:
                response = client.request(
                    method=request.method, url=request.url, # Use request attributes
                    headers=final_headers, **request_params
                )
                if update_session_from_response and session_to_use:
                     # Assuming an update method exists on AuthSession
                     update_method = getattr(session_to_use, 'update_session', None)
                     if update_method:
                         update_method(response.headers)
                     else:
                          print(f"Warning: AuthSession for user {getattr(session_to_use, 'user_id', 'Unknown')} has no 'update_session' method.")
            return response
        except httpx.RequestError as e:
            print(f"HTTP Request failed for {request.method} {request.url}: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during send: {e}")
            # Decide whether to raise or return None based on desired error handling
            return None # Returning None for consistency

# --- IntruderRequest Class (as provided) ---
class IntruderRequest(HTTPRequest):
    def __init__(self,
                 data: HTTPRequestData,
                 user_id: Optional[str] = None,
                 auth_info: Optional[RequestResources] = None) -> None: # Kept auth_info param name for compatibility
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


# --- AuthzTester Class ---

class AuthzTester:
    """
    Performs stateful authorization testing by ingesting requests
    and triggering cross-user/cross-resource tests.
    """
    def __init__(self, http_client: HTTPClient): # Inject HTTPClient
        # State: resource_type_name -> resource_id -> set(user_ids who accessed it)
        self.observed_access: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))

        # State: user_id -> AuthSession (holds cookies/tokens)
        self.user_sessions: Dict[str, AuthSession] = {}

        # State: action_identifier (e.g., URL) -> Base IntruderRequest for modification
        self.action_templates: Dict[str, IntruderRequest] = {}

        # State: resource_type_name -> set(action_identifier/URL)
        self.resource_type_actions: Dict[str, Set[str]] = defaultdict(set) # Added state

        # Log of performed tests to avoid duplicates (optional)
        self.performed_tests: Set[Tuple[str, str, str]] = set()

        # Log of potential findings
        self.findings: List[str] = []

        self.http_client = http_client # Store the client

    def _extract_info(self, request: IntruderRequest) -> Optional[Tuple[str, List[Tuple[str, str]], str]]:
        """Helper to extract user, resources (type_name, id), and action identifier."""
        user_id = request.user_id
        # Using URL as the primary action identifier, could be method+URL
        action_identifier = request.url

        if not user_id:
            # print(f"Warning: Request {request.url} lacks user_id. Skipping.")
            return None

        resources = []
        # Use attack_info["AUTH"]
        auth_info = request.attack_info.get("AUTH")
        if auth_info and auth_info.resources:
             for res in auth_info.resources:
                 # Ensure res.type exists before accessing res.type.name
                 if res.id and res.type and hasattr(res.type, 'name') and res.type.name:
                     resources.append((res.type.name, res.id))
                 # else: print(f"Warning: Incomplete resource info in request {request.url}.")

        if not resources:
             # print(f"Warning: Request {request.url} (User: {user_id}) lacks resource info. Skipping.")
             return None

        return user_id, resources, action_identifier

    def ingest(self, request: IntruderRequest):
        """Ingests a request, updates state, and triggers relevant AuthZ tests based on new user, action, or resource."""
        # print(f"\n--- Ingesting: {request.method} {request.url} (User: {request.user_id}) ---")

        extracted_info = self._extract_info(request)
        if not extracted_info:
            # print(f"Warning: Could not extract necessary info from request {request.url}. Skipping ingest.")
            return

        new_user_id, new_resources, new_action_url = extracted_info
        is_truly_new_user = new_user_id not in self.user_sessions
        user_session_added = False
        # Update user session if available in the request object
        if hasattr(request, "_auth_session") and request._auth_session:
            self.user_sessions[new_user_id] = request._auth_session
            user_session_added = True
            # print(f"  Stored/Updated session for user {new_user_id} from request {new_action_url}.")
        elif is_truly_new_user:
             print(f"Warning: No AuthSession found or provided for new user {new_user_id} during ingest of {new_action_url}. Tests requiring this session may fail.")

        # Store request as template for this action
        is_new_action_url = new_action_url not in self.action_templates
        self.action_templates[new_action_url] = request
        # print(f"  Stored/Updated action template for {new_action_url}.")

        # Identify resources belonging to already observed types and update state
        resources_in_observed_types = []
        for res_type_name, res_id in new_resources:
            if res_type_name in self.observed_access:
                 resources_in_observed_types.append((res_type_name, res_id))
            # Update observed access state
            self.observed_access[res_type_name][res_id].add(new_user_id)
            # Update resource type actions state
            self.resource_type_actions[res_type_name].add(new_action_url)
            # print(f"  Updated state: User '{new_user_id}' accessed Resource '{res_id}' (Type: {res_type_name}). Action '{new_action_url}' associated with type '{res_type_name}'.")

        # --- Trigger Tests ---
        all_users_with_sessions = set(self.user_sessions.keys())
        other_users_with_sessions = all_users_with_sessions - {new_user_id}

        # 1. If new_action_url observed: Try all other users on this new action + its associated resources
        if is_new_action_url:
             # print(f"  -> New Action Trigger: Testing action '{new_action_url}' for other users.")
             for user in other_users_with_sessions:
                 # Session existence already checked by using `other_users_with_sessions`
                 for res_type_name, res_id in new_resources:
                     test_sig = (user, res_id, new_action_url)
                     if test_sig not in self.performed_tests:
                         # print(f"    - Scheduling test (1): User '{user}', Resource '{res_id}', Action '{new_action_url}'")
                         self.run_test(user, res_id, new_action_url, res_type_name)
                         self.performed_tests.add(test_sig)

        # 2. If new_resource belongs to an existing resource_type: Try all existing actions for this type with the new resource, for all other users
        for res_type_name, res_id in resources_in_observed_types:
             # print(f"  -> Resource In Existing Type Trigger: Testing resource '{res_id}' (Type: {res_type_name}) with existing actions for other users.")
             actions_for_type = self.resource_type_actions.get(res_type_name, set())
             for existing_action_url in actions_for_type:
                 # Don't re-test the exact combination that triggered this ingest
                 if existing_action_url == new_action_url and (res_type_name, res_id) in new_resources:
                      continue

                 # Check if the base request for this existing_action_url actually mentions the resource type
                 base_req_for_action = self.action_templates.get(existing_action_url)
                 action_mentions_type = False
                 if base_req_for_action:
                      auth_info = base_req_for_action.attack_info.get("AUTH")
                      if auth_info and auth_info.resources:
                           for res in auth_info.resources:
                               if res.type and hasattr(res.type, "name") and res.type.name == res_type_name:
                                    action_mentions_type = True
                                    break
                 if not action_mentions_type:
                      # print(f"    - Skipping test: Action '{existing_action_url}' does not seem related to resource type '{res_type_name}'.")
                      continue

                 for user in other_users_with_sessions:
                     test_sig = (user, res_id, existing_action_url)
                     if test_sig not in self.performed_tests:
                         # print(f"    - Scheduling test (2): User '{user}', Resource '{res_id}', Action '{existing_action_url}'")
                         # Ensure the base request for the *existing_action_url* can be modified for *res_type_name*
                         if self.action_templates.get(existing_action_url): # Check if template exists
                              self.run_test(user, res_id, existing_action_url, res_type_name)
                              self.performed_tests.add(test_sig)
                         # else: print(f"    - Skipping test (2): No action template found for '{existing_action_url}'.")

        # 3. If new_user (and session was successfully added): Try all existing actions + their original associated resources for this new user
        if is_truly_new_user and user_session_added:
             # print(f"  -> New User Trigger: Testing user '{new_user_id}' against existing actions/resources.")
             for existing_action_url, base_template_request in self.action_templates.items():
                 # Extract original resource info from the template request's auth_info
                 template_auth_info = base_template_request.attack_info.get("AUTH")
                 if template_auth_info and template_auth_info.resources:
                     original_resources_for_action = []
                     for res in template_auth_info.resources:
                         if res.id and res.type and hasattr(res.type, "name") and res.type.name:
                             original_resources_for_action.append((res.type.name, res.id))
                         # else: print(f"    - Warning: Incomplete resource info in template for action '{existing_action_url}'.")

                     for orig_res_type_name, orig_res_id in original_resources_for_action:
                         # Don't test the action/resource pair that introduced this user via this specific request
                         is_introducing_resource = (existing_action_url == new_action_url and
                                                   (orig_res_type_name, orig_res_id) in [(rt, r_id) for rt, r_id in new_resources]) # Compare tuples
                         if is_introducing_resource:
                             continue

                         test_sig = (new_user_id, orig_res_id, existing_action_url)
                         if test_sig not in self.performed_tests:
                             # print(f"    - Scheduling test (3): User '{new_user_id}', Resource '{orig_res_id}', Action '{existing_action_url}'")
                             self.run_test(new_user_id, orig_res_id, existing_action_url, orig_res_type_name)
                             self.performed_tests.add(test_sig)
                 # else: print(f"  - Skipping action '{existing_action_url}' for new user test: No resource info found in template's auth_info.")

    def modify_request_for_resource(self, base_request: IntruderRequest, target_resource_id: str, resource_type_name: str) -> Optional[IntruderRequest]:
        """
        Creates a modified copy of the base request targeting the specific resource ID.
        Needs robust implementation based on how resource IDs appear in requests.
        """
        original_resource_id = None
        resource_location_info: Optional[Resource] = None # Type hint
        auth_info = base_request.attack_info.get("AUTH") # Use attack_info
        if auth_info and auth_info.resources:
            for res in auth_info.resources:
                 # Ensure res.type exists and has name attribute
                if res.type and hasattr(res.type, 'name') and res.type.name == resource_type_name and res.id:
                    original_resource_id = res.id
                    resource_location_info = res
                    break

        if not original_resource_id or not resource_location_info:
             print(f"      Error: Cannot find original resource ID or location info for type '{resource_type_name}' in base request {base_request.url}.")
             return None
        # Ensure request_part is accessible and valid enum member
        if not hasattr(resource_location_info, 'request_part') or not isinstance(resource_location_info.request_part, RequestPart):
             print(f"      Error: Invalid or missing 'request_part' in resource location info for {base_request.url}.")
             return None

        new_url = base_request.url
        new_post_data = base_request.post_data
        new_headers = base_request.headers.copy()
        modification_successful = False # Flag to track if modification occurred
        if resource_location_info.request_part == RequestPart.URL:
            if original_resource_id in new_url:
                 new_url = new_url.replace(original_resource_id, target_resource_id, 1)
                 modification_successful = True
                 # print(f"      Modified URL (naive replace): {new_url}")
            # else: print(f"      Warning: Could not find original ID '{original_resource_id}' in URL '{new_url}' for replacement.")

        elif resource_location_info.request_part == RequestPart.BODY:
            if new_post_data and original_resource_id in new_post_data:
                 new_post_data = new_post_data.replace(original_resource_id, target_resource_id, 1)
                 modification_successful = True
                 # print(f"      Modified POST data (naive replace)")
            # else: print(f"      Warning: Could not find original ID '{original_resource_id}' in POST data for replacement.")


        elif resource_location_info.request_part == RequestPart.HEADERS:
            raise Exception("Header params not currently supported!")
            # selected_slice should indicate which header
            # header_to_modify = None
            # if hasattr(resource_location_info, 'selected_slice') and isinstance(resource_location_info.selected_slice, dict):
            #      header_to_modify = resource_location_info.selected_slice.get(RequestPart.HEADERS) # Assuming key is the enum member

            # if header_to_modify and isinstance(header_to_modify, str) and header_to_modify.lower() in new_headers:
            #       original_value = new_headers[header_to_modify.lower()]
            #       if original_resource_id in original_value:
            #            new_headers[header_to_modify.lower()] = original_value.replace(original_resource_id, target_resource_id, 1)
            #            modification_successful = True
            #            # print(f"      Modified Header '{header_to_modify}' (naive replace)")
            #       # else: print(f"      Warning: Could not find original ID '{original_resource_id}' in Header '{header_to_modify}' value for replacement.")
            # # else: print(f"      Warning: Header '{header_to_modify}' for resource ID modification not found or invalid slice info.")


        if not modification_successful:
            print(f"      Warning: Failed to modify request for resource '{target_resource_id}' based on location info.")
            # Optionally return None if no modification was possible
            # return None


        # Create new data object with modifications
        # Provide default values for missing HTTPRequestData fields
        new_data = HTTPRequestData(
            method=base_request.method, url=new_url, headers=new_headers,
            post_data=new_post_data,
            is_iframe=base_request.is_iframe,
            redirected_from_url=None, # Add default
            redirected_to_url=None    # Add default
        )

        # Create a minimal IntruderRequest for the test
        # User ID and Auth Info are less relevant here, focus is on modified data
        # Pass None for auth_info to avoid carrying over original auth details
        test_request = IntruderRequest(data=new_data, user_id="TEST_RUNNER", auth_info=None)
        return test_request


    def run_test(self, user_to_impersonate: str, target_resource_id: str, action_url: str, resource_type_name: str):
        """Constructs, sends (using http_client), and analyzes a specific AuthZ test."""
        # print(f"  --- Running Test ---")
        # print(f"    User: {user_to_impersonate}")
        # print(f"    Target Resource: {target_resource_id} (Type: {resource_type_name})")
        # print(f"    Action URL: {action_url}")

        # 1. Get Auth Session
        user_session = self.user_sessions.get(user_to_impersonate)
        if not user_session:
            print(f"    Error: No session for user '{user_to_impersonate}'. Cannot run test.")
            return

        # 2. Get Base Request Template
        base_request = self.action_templates.get(action_url)
        if not base_request:
            print(f"    Error: No template for action '{action_url}'.")
            return

        # 3. Modify Request
        modified_request = self.modify_request_for_resource(base_request, target_resource_id, resource_type_name)
        if not modified_request:
             print(f"    Error: Failed to modify request.")
             return

        # 4. Send Request using the injected HTTPClient
        # print(f"    Sending: {modified_request.method} {modified_request.url} as User '{user_to_impersonate}' via HTTPClient")
        try:
            # Pass the modified request and the specific user's session
            response = self.http_client.send(request=modified_request, auth_session=user_session)

            # 5. Analyze Response
            if response is None:
                # HTTPClient.send already prints error details
                result = f"FAIL (Send Error) - User '{user_to_impersonate}', Resource '{target_resource_id}', Action '{action_url}'"
                print(f"    Result: Request failed to send.")
            else:
                status = response.status_code
                # print(f"    Response Status: {status}")
                if 200 <= status < 300:
                    # Check response content for confirmation if possible
                    result = f"!!!! POTENTIAL BYPASS !!!! User '{user_to_impersonate}' accessed Resource '{target_resource_id}' via Action '{action_url}' (Status: {status})"
                    print(f"    {result}")
                    self.findings.append(result)
                elif status in [401, 403]:
                    result = f"OK (Denied {status}) - User '{user_to_impersonate}', Resource '{target_resource_id}', Action '{action_url}'"
                    # print(f"    Result: Access Denied (Status: {status}).")
                elif 300 <= status < 400:
                    loc = response.headers.get('location', 'N/A')
                    result = f"INFO (Redirect {status} to {loc}) - User '{user_to_impersonate}', Resource '{target_resource_id}', Action '{action_url}'"
                    # print(f"    Result: Redirect {status} to {loc}. Needs analysis.")
                else:
                    result = f"INFO (Status {status}) - User '{user_to_impersonate}', Resource '{target_resource_id}', Action '{action_url}'"
                    # print(f"    Result: Status {status}. Needs analysis.")

        except Exception as e:
            # Catch potential exceptions from http_client.send if it raises them
            result = f"FAIL (Exception during send processing: {e}) - User '{user_to_impersonate}', Resource '{target_resource_id}', Action '{action_url}'"
            print(f"    Error during request processing: {e}")

        # print(f"    Test Result Logged: {result}") # Logged internally via self.findings