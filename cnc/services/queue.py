from typing import Dict, Any
from collections import defaultdict
from helpers.queue import Channel

class QueueRegistry:
    def __init__(self, reset: bool = False):
        if reset:
            self.channels = defaultdict(Channel)
        else:
            # Singleton pattern
            if not hasattr(QueueRegistry, "_instance"):
                QueueRegistry._instance = self
                self.channels: Dict[str, Channel[Any]] = defaultdict(Channel)
            else:
                self.channels = QueueRegistry._instance.channels

    def get(self, name: str) -> Channel[Any]:
        return self.channels[name]


# Importable singleton
queues = QueueRegistry()