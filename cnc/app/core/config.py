from pydantic import PostgresDsn, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # postgres_dsn: PostgresDsn # Comment out postgres
    sqlite_db_url: str = "sqlite+aiosqlite:///./pentest.db" # Add sqlite url
    agent_binary: str = "/opt/agent/bin/run"
    
    class Config:
        env_file = ".env"


settings = Settings(
    # postgres_dsn="postgresql+asyncpg://postgres:postgres@localhost/pentest", # Remove postgres init
    _env_file=".env",
)