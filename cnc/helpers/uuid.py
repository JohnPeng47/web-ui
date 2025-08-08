import uuid
from typing import Union
from uuid import UUID


def generate_uuid() -> UUID:
    """Generate a random UUID."""
    return uuid.uuid4()


def is_valid_uuid(uuid_to_test: Union[str, UUID]) -> bool:
    """Check if the provided string is a valid UUID."""
    try:
        uuid_obj = uuid.UUID(str(uuid_to_test))
        return True
    except (ValueError, AttributeError):
        return False