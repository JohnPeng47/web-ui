from app.core.registry import register_enricher
from app.domain.schemas import UserCtx
from app.protocol import AttackData, ResourceLocator, RequestPart
from app.services.enrichment import RequestEnrichmentWorker
from app.protocol.http import HTTPRequestData


@register_enricher
class DefaultEnricher(RequestEnrichmentWorker):
    name = "default-enricher"

    async def enrich(self, request: HTTPRequestData, user: UserCtx) -> AttackData:
        """
        Basic enrichment that extracts resource locators from the request.
        """
        locators = []
        
        # Extract URL as a resource locator
        locators.append(
            ResourceLocator(
                id=request.url,
                request_part=RequestPart.URL,
                type_name="url"
            )
        )
        
        # Extract headers as resource locators
        for header_name, header_value in request.headers.items():
            locators.append(
                ResourceLocator(
                    id=f"{header_name}:{header_value}",
                    request_part=RequestPart.HEADER,
                    type_name="header"
                )
            )
        
        # Extract body data if present
        if request.post_data:
            locators.append(
                ResourceLocator(
                    id=request.post_data,
                    request_part=RequestPart.BODY,
                    type_name="body"
                )
            )
        
        return AttackData(request=request, locators=locators)