import os
from pathlib import Path
from typing import AsyncGenerator

from contextlib import asynccontextmanager
from sqlmodel import SQLModel, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DB_PATH = Path(__file__).parent.parent / "pentest_hub.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite+aiosqlite:///./{str(DB_PATH)}")

engine = create_async_engine(DATABASE_URL, echo=False)

async def create_db_and_tables():
    async with engine.begin() as conn:            
        tables = await conn.run_sync(
            lambda c: c.exec_driver_sql("SELECT name FROM sqlite_master").fetchall()
        )
        print("SQLite tables:", tables)

        await conn.run_sync(SQLModel.metadata.create_all)
        

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

@asynccontextmanager
async def override_db(db_url: str):
    """Context manager for testing to override the default database URL."""
    global engine
    original_engine = engine
    engine = create_async_engine(db_url, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        yield
    finally:
        engine = original_engine