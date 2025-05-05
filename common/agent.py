from pydantic import BaseModel

class UserCreds(BaseModel):
    user_name: str
    role: str