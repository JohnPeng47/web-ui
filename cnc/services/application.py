from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from cnc.database import crud
from cnc.schemas.application import ApplicationCreate, Finding
from cnc.database.models import Application


async def create_app(db: AsyncSession, app_data: ApplicationCreate) -> Application:
    """Create a new application."""
    return await crud.create_application(db, app_data)


async def get_app(db: AsyncSession, app_id: UUID) -> Application:
    """Get an application by ID."""
    app = await crud.get_application(db, app_id)
    if not app:
        raise ValueError(f"Application with ID {app_id} not found")
    return app


async def add_finding(db: AsyncSession, app_id: UUID, finding: Finding) -> Application:
    """Add a security finding to an application."""
    app = await crud.get_application(db, app_id)
    if not app:
        raise ValueError(f"Application with ID {app_id} not found")
    
    # Convert finding to a dictionary
    finding_dict = finding.dict()
    
    # Initialize findings list if it doesn't exist
    if app.findings is None:
        app.findings = []
    
    # Add the new finding
    app.findings.append(finding_dict)
    
    # Update the application
    updated_app = await crud.update_application(db, app)
    return updated_app