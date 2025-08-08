from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from schemas.application import ApplicationCreate, ApplicationOut, AddFindingRequest
from database.session import get_session
from services import application as app_service
from cnc.services.queue import BroadcastChannel
from httplib import HTTPMessage


def make_application_router() -> APIRouter:
    """
    Create the application router with injected dependencies.
    
    Returns:
        Configured APIRouter instance
    """
    router = APIRouter(prefix="/application")
    
    @router.post("/", response_model=ApplicationOut)
    async def create_app(payload: ApplicationCreate, db: AsyncSession = Depends(get_session)):
        """Create a new application."""
        try:
            app = await app_service.create_app(db, payload)
            return app
        except Exception as e:
            print(e)
            raise HTTPException(status_code=400, detail=str(e))
    
    
    @router.get("/{app_id}", response_model=ApplicationOut)
    async def get_app(app_id: UUID, db: AsyncSession = Depends(get_session)):
        """Get an application by ID."""
        try:
            app = await app_service.get_app(db, app_id)
            return app
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/{app_id}/findings", response_model=ApplicationOut)
    async def add_finding(app_id: UUID, payload: AddFindingRequest, db: AsyncSession = Depends(get_session)):
        """Add a security finding to an application."""
        try:
            app = await app_service.add_finding(db, app_id, payload.finding)
            return app
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    return router

# Legacy support - for backward compatibility during transition
router = make_application_router()  # type: ignore