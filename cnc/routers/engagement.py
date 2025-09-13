from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from cnc.schemas.engagement import EngagementCreate, EngagementOut, AddFindingRequest, PageDataMergeRequest, EngagementPageDataOut
from cnc.database.session import get_session

from cnc.database.crud import (
    create_engagement as create_engagement_service, 
    get_engagement as get_engagement_service, 
    update_engagement as update_engagement_service,
)
from cnc.services.engagement import merge_page_data as merge_page_data_service

def make_engagement_router() -> APIRouter:
    """
    Create the application router with injected dependencies.
    
    Returns:
        Configured APIRouter instance
    """
    router = APIRouter()
    
    @router.post("/engagement/", response_model=EngagementOut)
    async def create_engagement(payload: EngagementCreate, db: AsyncSession = Depends(get_session)):
        """Create a new engagement."""
        try:
            app = await create_engagement_service(db, payload)
            return app
        except Exception as e:
            print(e)
            raise HTTPException(status_code=400, detail=str(e))
    
    
    @router.get("/engagement/{engagement_id}", response_model=EngagementOut)
    async def get_engagement(engagement_id: UUID, db: AsyncSession = Depends(get_session)):
        """Get an engagement by ID."""
        try:
            app = await get_engagement_service(db, engagement_id)
            return app
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/engagement/{engagement_id}/page-data", response_model=EngagementPageDataOut)
    async def merge_page_data(
        engagement_id: UUID,
        payload: PageDataMergeRequest,
        db: AsyncSession = Depends(get_session),
    ):
        """Merge page_data delta into engagement-level page_data."""
        try:
            updated = await merge_page_data_service(db, engagement_id, payload.delta)
            return EngagementPageDataOut(page_data=updated)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # @router.post("/{engagement_id}/findings", response_model=EngagementOut)
    # async def add_finding(engagement_id: UUID, payload: AddFindingRequest, db: AsyncSession = Depends(get_session)):
    #     """Add a security finding to an engagement."""
    #     try:
    #         app = await add_engagement_finding_service(db, engagement_id, payload.finding)
    #         return app
    #     except ValueError as e:
    #         raise HTTPException(status_code=404, detail=str(e))
    #     except Exception as e:
    #         raise HTTPException(status_code=500, detail=str(e))
            
    return router

# Legacy support - for backward compatibility during transition
router = make_engagement_router()  # type: ignore