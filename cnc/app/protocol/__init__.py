from dataclasses import dataclass
from typing import Sequence, Optional
from uuid import UUID

from .http import HTTPRequestData, ResourceLocator, RequestPart


@dataclass(slots=True, frozen=True)
class AttackData:
    """
    Generic payload delivered to any AttackWorker.
    Extra analysis information can be attached later without
    changing the workers' public signature.
    """
    request: HTTPRequestData
    locators: Sequence[ResourceLocator]
    correlation_id: Optional[UUID] = None