from typing import Optional, Dict, Any, Type # Added Type
import httpx # Import httpx
import json # For potential JSON post data handling


# --- Placeholder/Assumed Classes ---
# (These would typically be defined properly elsewhere with more robust logic)

class HTTPRequestData:
    """Simple data structure to hold request details."""
    def __init__(self, method: str, url: str, headers: Dict[str, str],
                 post_data: Optional[str], redirected_from_url: Optional[str],
                 redirected_to_url: Optional[str], is_iframe: bool):
        self.method = method
        self.url = url
        # Ensure headers keys are lowercase for consistency, httpx/browsers often normalize
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.post_data = post_data
        self.redirected_from_url = redirected_from_url
        self.redirected_to_url = redirected_to_url
        self.is_iframe = is_iframe

class AuthSession:
    """
    Placeholder for authentication session management.
    In a real implementation, this would handle cookie persistence,
    token refresh, etc., possibly using httpx.Cookies or http.cookiejar.
    """
    def __init__(self, initial_headers: Dict[str, str], initial_cookies: Optional[Dict[str, str]] = None):
        self._cookies = initial_cookies if initial_cookies is not None else {}
        self._auth_headers = {} # e.g., {'authorization': 'Bearer ...'}

        # Example: Basic extraction of cookies from initial headers
        # A robust solution needs proper cookie parsing (httpx.Cookies, http.cookies)
        cookie_header = initial_headers.get('cookie')
        if cookie_header:
            try:
                # VERY basic parsing - assumes simple key=value pairs separated by ';'
                # Does NOT handle attributes like Path, Domain, Expires, HttpOnly etc.
                for item in cookie_header.split(';'):
                    if '=' in item:
                        key, value = item.strip().split('=', 1)
                        if key not in self._cookies: # Avoid overwriting explicit initial_cookies
                            self._cookies[key] = value
            except Exception as e:
                 print(f"Warning: Basic cookie parsing failed for header '{cookie_header}': {e}")

        # Example: Maybe store an initial Authorization header if present
        auth_header = initial_headers.get('authorization')
        if auth_header:
            self._auth_headers['authorization'] = auth_header

    def get_cookies(self) -> Dict[str, str]:
        """Returns cookies associated with the session."""
        return self._cookies.copy() # Return a copy

    def get_headers(self) -> Dict[str, str]:
        """Returns session-specific headers (e.g., Authorization)"""
        # In a real scenario, this might refresh tokens if needed
        return self._auth_headers.copy() # Return a copy

    def update_session(self, response_headers: httpx.Headers):
         """
         Update session state (e.g., cookies) from response headers.
         Needs a robust cookie handling library for proper implementation.
         """
         # Example: Update cookies from Set-Cookie headers using httpx's parsing
         # This is still simplified as it doesn't handle domain/path matching well
         # without a full cookie jar implementation.
         for key, value in response_headers.multi_items():
             if key.lower() == 'set-cookie':
                 try:
                     # Basic parsing of the cookie value part
                     cookie_part = value.split(';')[0]
                     if '=' in cookie_part:
                         name, val = cookie_part.strip().split('=', 1)
                         self._cookies[name] = val
                         # print(f"Debug: Updated cookie {name}={val}") # Debug print
                 except Exception as e:
                     print(f"Warning: Could not parse Set-Cookie value '{value}': {e}")


# --- Modified HTTPRequest Class ---

# Forward reference for type hinting Request inside the class
Request = Type["HTTPRequest"]

class HTTPRequest:
    """
    HTTP request class with unified implementation and sending capability.
    """
    # Corrected constructor name from 'init' to '__init__'
    def __init__(self, data: HTTPRequestData):
        self._data = data
        # Initialize AuthSession, passing initial headers for potential cookie/auth extraction
        self._auth_session = AuthSession(self._data.headers)

    @property
    def method(self) -> str:
        return self._data.method

    @property
    def url(self) -> str:
        return self._data.url

    @property
    def headers(self) -> Dict[str, str]:
        # Return a copy to prevent external modification of internal state
        return self._data.headers.copy()

    @property
    def post_data(self) -> Optional[str]:
        # Could potentially be bytes as well, depending on source
        return self._data.post_data

    @property
    def redirected_from(self) -> Optional[Request]:
        if self._data.redirected_from_url:
            # Create minimal request object for redirect marker
            # Avoid full __init__ to prevent creating unnecessary AuthSession
            data = HTTPRequestData(
                method="", # Method isn't relevant for just representing the source URL
                url=self._data.redirected_from_url,
                headers={}, post_data=None, redirected_from_url=None,
                redirected_to_url=None, is_iframe=False
            )
            req = object.__new__(HTTPRequest) # Create instance without calling __init__
            req._data = data
            req._auth_session = None # No auth session needed for this marker object
            return req
        return None

    @property
    def redirected_to(self) -> Optional[Request]:
        if self._data.redirected_to_url:
            # Create minimal request object for redirect marker
            data = HTTPRequestData(
                method="", url=self._data.redirected_to_url,
                headers={}, post_data=None, redirected_from_url=None,
                redirected_to_url=None, is_iframe=False
            )
            req = object.__new__(HTTPRequest) # Create instance without calling __init__
            req._data = data
            req._auth_session = None # No auth session needed for this marker object
            return req
        return None

    @property
    def is_iframe(self) -> bool:
        return self._data.is_iframe

    def to_json(self) -> Dict[str, Any]:
        # Exclude non-serializable _auth_session
        return {
            "method": self.method,
            "url": self.url,
            "headers": self.headers,
            "post_data": self.post_data,
            "redirected_from": self._data.redirected_from_url,
            "redirected_to": self._data.redirected_to_url,
            "is_iframe": self.is_iframe
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> Request:
        request_data = HTTPRequestData(
            method=data["method"],
            url=data["url"],
            headers=data["headers"],
            post_data=data.get("post_data"), # Use .get for robustness
            redirected_from_url=data.get("redirected_from"),
            redirected_to_url=data.get("redirected_to"),
            is_iframe=data.get("is_iframe", False)
        )
        # Creates a new default AuthSession based on the loaded headers
        return cls(request_data)

    # Assuming 'pw_request' comes from Playwright's Request object
    # from playwright.sync_api import Request as PlaywrightRequest # Example import
    # @classmethod
    # def from_pw(cls, pw_request: PlaywrightRequest) -> "HTTPRequest":
    #     headers = dict(pw_request.headers) # Get headers as dict
    #     request_data = HTTPRequestData(
    #         method=pw_request.method,
    #         url=pw_request.url,
    #         headers=headers,
    #         post_data=pw_request.post_data, # Note: Playwright post_data might be bytes
    #         redirected_from_url=pw_request.redirected_from.url if pw_request.redirected_from else None,
    #         redirected_to_url=pw_request.redirected_to.url if pw_request.redirected_to else None,
    #         is_iframe=bool(pw_request.frame.parent_frame)
    #     )
    #     return cls(request_data)

    def to_str(self) -> str:
        """String representation of HTTP request"""
        req_str = "[Request]: \n"
        req_str += f"{self.method} {self.url}\n"
        redirected_from = self.redirected_from # Call property once
        if redirected_from:
            req_str += f"Redirected from: {redirected_from.url}\n"
        redirected_to = self.redirected_to # Call property once
        if redirected_to:
            req_str += f"Redirecting to: {redirected_to.url}\n" # Corrected typo
        if self.is_iframe:
            req_str += "From iframe\n"

        req_str += "Headers:\n"
        headers = self.headers # Use property to get current headers
        for k,v in headers.items():
            # Avoid printing potentially sensitive cookies directly if managed by AuthSession
            if k.lower() != 'cookie':
                 req_str += f"  {k}: {v}\n"

        # Optionally show cookies from the session if needed for debugging
        # if self._auth_session:
        #    cookies = self._auth_session.get_cookies()
        #    if cookies:
        #        req_str += "Session Cookies:\n"
        #        for k, v in cookies.items():
        #            req_str += f"  {k}={v}\n"


        if self.post_data:
             # Basic check if post_data looks like JSON for nicer printing
             try:
                 parsed_json = json.loads(self.post_data)
                 pretty_json = json.dumps(parsed_json, indent=2)
                 req_str += f"Post Data (JSON):\n{pretty_json}\n"
             except (json.JSONDecodeError, TypeError):
                 req_str += f"Post Data:\n{self.post_data}\n"
        else:
             req_str += "No Post Data\n"

        return req_str

    # --- New send method ---
    def send(self, auth_session: Optional[AuthSession] = None,
             follow_redirects: bool = True, timeout: float = 30.0,
             update_session_from_response: bool = True) -> Optional[httpx.Response]:
        """
        Sends the HTTP request using httpx.

        Args:
            auth_session: An optional AuthSession object to use for sending the
                          request. If None, the request's own internal session state
                          (self._auth_session) is used.
            follow_redirects: Whether httpx should automatically follow redirects.
            timeout: Request timeout in seconds.
            update_session_from_response: If True, attempts to update the cookies
                                          in the used AuthSession based on the
                                          response's Set-Cookie headers.

        Returns:
            An httpx.Response object if the request is successful, otherwise None
            if an httpx.RequestError occurs (or raises other exceptions).
        """
        session_to_use = auth_session or self._auth_session

        if not session_to_use:
            # This might happen if the request was created minimally (e.g., redirect marker)
            print("Warning: Sending request without a valid AuthSession. Relying solely on original headers.")
            session_cookies = {}
            session_headers = {}
        else:
            session_cookies = session_to_use.get_cookies()
            session_headers = session_to_use.get_headers()

        # Combine headers: Start with original request headers (lowercased),
        # then overlay session-specific headers (e.g., Authorization).
        final_headers = self.headers # Gets a lowercased copy via property
        final_headers.update(session_headers) # Session headers override originals

        # Remove 'cookie' header if we are passing cookies via the `cookies` param.
        # httpx prefers the `cookies` argument.
        final_headers.pop('cookie', None)

        # Determine how to send post_data
        request_params = {}
        content_type = final_headers.get('content-type', '').lower()

        if self.post_data is not None:
            # Basic check for JSON content type
            if 'application/json' in content_type:
                try:
                    # Assume post_data is a JSON string, parse it for httpx
                    request_params['json'] = json.loads(self.post_data)
                except (json.JSONDecodeError, TypeError):
                    # If it's not valid JSON, send as raw data
                    print(f"Warning: Content-Type is JSON, but post_data is not valid JSON. Sending as raw data.")
                    request_params['content'] = self.post_data # Use 'content' for raw body
            # Basic check for form data
            elif 'application/x-www-form-urlencoded' in content_type:
                 # httpx 'data' param handles dicts for form encoding
                 # We'd need to parse self.post_data string into a dict here.
                 # For simplicity, let's send as raw content if it's a string.
                 # If post_data was guaranteed to be a dict for forms, we'd use 'data'.
                 request_params['content'] = self.post_data # Send raw string
            else:
                 # Default to sending as raw content (bytes or string)
                 request_params['content'] = self.post_data

        try:
            # Use a context manager for the client for connection pooling
            with httpx.Client(follow_redirects=follow_redirects, timeout=timeout,
                              cookies=session_cookies) as client: # Pass cookies to client
                response = client.request(
                    method=self.method,
                    url=self.url,
                    headers=final_headers,
                    # Pass content/json/data as determined above
                    **request_params
                )

                # Update the session used with information from the response (e.g., Set-Cookie)
                if update_session_from_response and session_to_use:
                     session_to_use.update_session(response.headers)


            return response

        except httpx.RequestError as e:
            print(f"HTTP Request failed for {self.method} {self.url}: {e}")
            # Decide error handling: return None or re-raise
            return None
        except json.JSONDecodeError as e:
             print(f"Error decoding post_data as JSON for {self.method} {self.url}: {e}")
             return None # Failed pre-request processing
        except Exception as e:
            # Catch other potential errors (e.g., within AuthSession logic if complex)
            print(f"An unexpected error occurred during send: {e}")
            raise # Re-raise unexpected errors


# --- Example Usage ---
if __name__ == '__main__':
    # 1. Create a request (e.g., from JSON or manually)
    req_data_dict = {
        "method": "GET",
        "url": "https://httpbin.org/cookies/set?mycookie=myvalue",
        "headers": {"User-Agent": "MyHTTPRequestClient/1.0", "Accept": "*/*"},
        "post_data": None,
        "redirected_from": None,
        "redirected_to": None,
        "is_iframe": False
    }
    http_request = HTTPRequest.from_json(req_data_dict)
    print("--- Original Request ---")
    print(http_request.to_str())

    # 2. Send the request using its internal session
    print("\n--- Sending request (initial)... ---")
    response1 = http_request.send(follow_redirects=True)

    if response1:
        print(f"Status Code: {response1.status_code}")
        # print(f"Response Body: {response1.text}")
        print(f"Response Cookies: {response1.cookies.items()}")
        # The internal _auth_session should now have 'mycookie' if update_session worked
        print(f"Internal session cookies after request 1: {http_request._auth_session.get_cookies()}")
    else:
        print("Request 1 failed.")

    # 3. Create another request that should see the cookie
    req_data_dict_2 = {
        "method": "GET",
        "url": "https://httpbin.org/cookies",
        "headers": {"User-Agent": "MyHTTPRequestClient/1.0"},
        "post_data": None, "redirected_from": None, "redirected_to": None, "is_iframe": False
    }
    http_request_2 = HTTPRequest.from_json(req_data_dict_2)
    print("\n--- Sending request 2 (using original request's session)... ---")
    # Send request 2, explicitly using the session from the *first* request object
    # This simulates sending subsequent requests within the same logical session
    response2 = http_request_2.send(auth_session=http_request._auth_session)

    if response2:
        print(f"Status Code: {response2.status_code}")
        print(f"Response Body: {response2.text}") # Should show 'mycookie'
    else:
        print("Request 2 failed.")

    # 4. Create a separate session and send request 2 with it
    print("\n--- Sending request 2 (using a NEW session)... ---")
    new_auth_session = AuthSession(initial_headers={}, initial_cookies={'othercookie': 'othervalue'})
    response3 = http_request_2.send(auth_session=new_auth_session)

    if response3:
        print(f"Status Code: {response3.status_code}")
        print(f"Response Body: {response3.text}") # Should show 'othercookie', not 'mycookie'
    else:
        print("Request 3 failed.")

    # 5. Example POST request with JSON
    post_req_data = {
        "method": "POST",
        "url": "https://httpbin.org/post",
        "headers": {"User-Agent": "MyHTTPRequestClient/1.0", "Content-Type": "application/json"},
        "post_data": '{"key": "value", "number": 123}', # Post data as JSON string
        "redirected_from": None, "redirected_to": None, "is_iframe": False
    }
    post_request = HTTPRequest.from_json(post_req_data)
    print("\n--- Sending POST request with JSON ---")
    print(post_request.to_str())
    post_response = post_request.send()
    if post_response:
        print(f"Status Code: {post_response.status_code}")
        try:
            print(f"Response JSON Body:\n{json.dumps(post_response.json(), indent=2)}")
        except json.JSONDecodeError:
             print(f"Response Body (non-JSON):\n{post_response.text}")

    else:
        print("POST Request failed.")