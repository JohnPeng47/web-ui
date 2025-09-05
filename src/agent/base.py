from enum import Enum

class AgentType(str, Enum):
    DISCOVERY = "discovery"
    EXPLOIT = "exploit"