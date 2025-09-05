from enum import Enum
from typing import Dict, Any

from cnc.schemas.base import JSONModel

class UserRoleCredentialsType(str, Enum):
    PASSWORD = "password"

class UserCredentialsBase(JSONModel):
    type: UserRoleCredentialsType

    def to_dict(self) -> Dict[str, Any]:
        return {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserCredentialsBase":
        return cls(type=data["type"])
    
# Derived credential classes
class PasswordCredentials(UserCredentialsBase):
    type: UserRoleCredentialsType = UserRoleCredentialsType.PASSWORD
    username: str
    password: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "username": self.username,
            "password": self.password
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PasswordCredentials":
        return cls(
            type=data["type"],
            username=data["username"],
            password=data["password"]
        )