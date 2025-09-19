from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import Dict, Any

class DerivedJSONModel(BaseModel, ABC):
    """Used for implementing derived fields and their serialization/deserialization"""
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DerivedJSONModel":
        return cls(**data)