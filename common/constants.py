from pathlib import Path

# temp holding place for application constants, which may or may not be configurable
# exploit agent
MAX_EXPLOIT_AGENT_STEPS = 3

# discovery agent 
MAX_DISCOVERY_AGENT_STEPS = 6
MAX_DISCOVERY_PAGE_STEPS = 15
SCREENSHOTS = False

# server workers
BROWSER_PROXY_HOST = "127.0.0.1"
BROWSER_PROXY_PORT = 8081
BROWSER_CDP_HOST = "127.0.0.1"
BROWSER_CDP_PORT = 9899
BROWSER_PROFILE_DIR = Path(
    r"C:\Users\jpeng\AppData\Local\Google\Chrome\User Data\Profile 2"
)
BROWSER_PROFILE_DIR_2 = Path(
    r".profiles"
)

# cnc server url
API_SERVER_HOST = "127.0.0.1"
API_SERVER_PORT = 8000

# detection prompt
NUM_SCHEDULED_ACTIONS = 5

# llm configurations
SERVER_MODEL_CONFIG = {
    "model_config": {
        "detection": "gpt-4.1"
    }
}
DISCOVERY_MODEL_CONFIG = {
    "model_config": {
        "browser_use": "gpt-4.1",
        "update_plan": "o3-mini",
        "create_plan": "o3-mini",
        "check_plan_completion": "gpt-4.1",
    }
}
EXPLOIT_MODEL_CONFIG = {
    "model_config": {
        "classify-steps": "o4-mini",
        "agent": "gpt-4.1"
    }
}

# manual approval for exploit agents
MANUAL_APPROVAL_EXPLOIT_AGENT: bool = True

# logging
SERVER_LOG_DIR = ".server_logs"