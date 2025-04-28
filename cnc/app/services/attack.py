import abc
from typing import Set

from app.domain.schemas import UserCtx
from app.protocol import AttackData


class AttackWorker(abc.ABC):
    name: str
    consumes: Set[str]  # names of enrichment workers

    @abc.abstractmethod
    async def ingest(self, *, user: UserCtx, data: AttackData) -> None:
        pass