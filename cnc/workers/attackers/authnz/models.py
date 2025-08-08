from pydantic import BaseModel
from cnc.services.attack import Attack

class PlannedTest(BaseModel):
    user: str
    resource_id: str | None
    action: str
    type_name: str | None

class AuthNZAttack(Attack):
    type: str = "AuthNZ Attack"
    description: str = "Authorization or Authentication attack"
    attack_info: PlannedTest

class HorizontalUserAuthz(AuthNZAttack):
    sub_type: str = "Horizontal User Action"
    description: str = "Swapping to same user role on action"

class VerticalUserAuthz(AuthNZAttack):
    sub_type: str = "Vertical User Action"
    description: str = "Swapping to different user role on action"

class HorizontalResourceAuthz(AuthNZAttack):
    sub_type: str = "Horizontal Resource"
    description: str = "Swapping resource id for the same action, across the same role"

class VerticalResourceAuthz(AuthNZAttack):
    sub_type: str = "Vertical Resource"
    description: str = "Swapping resource id for the same action, across different roles"