import abc
from app.domain.schemas import UserCtx
from app.protocol import AttackData, HTTPRequestData


class RequestEnrichmentWorker(abc.ABC):
    name: str

    @abc.abstractmethod
    async def enrich(
        self, request: HTTPRequestData, user: UserCtx
    ) -> AttackData:
        """
        MUST return an AttackData instance.
        Test-case: implementers must ensure locators are preserved (test #2).
        """
        pass