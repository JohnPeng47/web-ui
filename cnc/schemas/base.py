from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import Dict, Any

class JSONModel(BaseModel, ABC):
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONModel":
        return cls(**data)