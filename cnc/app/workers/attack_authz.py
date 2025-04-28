from app.core.registry import register_attacker
from app.domain.schemas import UserCtx
from app.protocol import AttackData
from app.services.attack import AttackWorker
from app.core.logging import get_logger

logger = get_logger(__name__)


class AuthzTester:
    """
    Placeholder for the supplied AuthzTester class that would be imported from
    an external library or module. This is a simple mock implementation.
    """
    def ingest(self, user, request, resource_locators, session=None):
        logger.info(
            f"AuthzTester.ingest called with user={user}, "
            f"url={request.url}, locators={len(resource_locators)}"
        )
        # In a real implementation, this would perform authorization testing


@register_attacker
class AuthzAttackWorker(AttackWorker):
    name = "authz"
    consumes = {"default-enricher"}

    def __init__(self):
        self.tester = AuthzTester()

    async def ingest(self, *, user: UserCtx, data: AttackData) -> None:
        """
        Process the enriched request data and check for authorization issues.
        """
        self.tester.ingest(
            user=user.username,
            request=data.request,
            resource_locators=data.locators,
            session=user.session,
        )