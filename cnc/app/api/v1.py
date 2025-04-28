import json
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db, get_bus
from app.domain.models import Application, AppUser
from app.domain.schemas import UserCtx
from app.services.eventbus import EventBus

router = APIRouter(prefix="/v1")


class InitAppBody(BaseModel):
    name: str
    users: List[UserCtx]


@router.post("/applications", status_code=status.HTTP_201_CREATED)
async def init_application(body: InitAppBody, db: AsyncSession = Depends(get_db)):
    app_row = Application(name=body.name)
    db.add(app_row)
    await db.flush()

    for u in body.users:
        db.add(AppUser(**u.model_dump(), application_id=app_row.id))
    await db.commit()
    return {"id": app_row.id}


class RawRequestBody(BaseModel):
    app_id: UUID
    user_id: UUID
    request: dict  # JSON serialised HTTPRequest


@router.post("/traffic")
async def ingest_traffic(body: RawRequestBody, bus: EventBus = Depends(get_bus)):
    await bus.publish_raw({
        "payload": json.dumps(body.request),
        "user": json.dumps({"id": str(body.user_id)}),
        "enricher": "default-enricher",
    })
    return {"status": "queued"}