from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from database import crud
from schemas.application import ApplicationCreate, ApplicationOut
from database.models import Application


async def create_app(db: AsyncSession, app_data: ApplicationCreate) -> Application:
    """Create a new application."""
    return await crud.create_application(db, app_data)


async def get_app(db: AsyncSession, app_id: UUID) -> Application:
    """Get an application by ID."""
    app = await crud.get_application(db, app_id)
    if not app:
        raise ValueError(f"Application with ID {app_id} not found")
    return app