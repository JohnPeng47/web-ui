from fastapi import Depends, FastAPI, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.services.eventbus import EventBus


async def get_db(request: Request) -> AsyncSession:
    return request.app.state.db


async def get_bus(request: Request) -> EventBus:
    return request.app.state.bus