from pydantic import BaseModel
from typing import Optional

class AttackResult(BaseModel):
    success: bool
    result: Optional[str]
    description: Optional[str]

# TODO: check during ingestion later that result is set
class Attack(BaseModel):
    type: str
    description: str
    attack_info: BaseModel
    sub_type: Optional[str] = None
    result: Optional[AttackResult] = None