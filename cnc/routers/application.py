from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from schemas.application import ApplicationCreate, ApplicationOut
from database.session import get_session
from services import application as app_service

router = APIRouter(prefix="/application")


@router.post("/", response_model=ApplicationOut)
async def create_app(payload: ApplicationCreate, db: AsyncSession = Depends(get_session)):
    """Create a new application."""
    try:
        app = await app_service.create_app(db, payload)
        return app
    except Exception as e:
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