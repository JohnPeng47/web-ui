from pathlib import Path

# temp holding place for application constants, which may or may not be configurable
# exploit agent
MAX_EXPLOIT_AGENT_STEPS = 12

# discovery agent 
MAX_DISCOVERY_AGENT_STEPS = 10
MAX_DISCOVERY_PAGE_STEPS = 10
SCREENSHOTS = False

# server workers
BROWSER_PROXY_HOST = "127.0.0.1"
BROWSER_PROXY_PORT = 8081
BROWSER_CDP_HOST = "127.0.0.1"
BROWSER_CDP_PORT = 9899
BROWSER_PROFILE_DIR = Path(
    r"C:\Users\jpeng\AppData\Local\Google\Chrome\User Data\Profile 2"
)

# cnc server url
API_SERVER_HOST = "0.0.0.0"
API_SERVER_PORT = 8000