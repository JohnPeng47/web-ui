from enum import Enum
from pydantic import BaseModel
from typing import Dict, Any

class UserRoleCredentialsType(str, Enum):
    PASSWORD = "password"

class UserRoleCredentials(BaseModel):
    type: UserRoleCredentialsType
    username: str
    password: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "username": self.username,
            "password": self.password
        }