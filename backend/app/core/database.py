from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

parsed_db_url = urlparse(settings.DATABASE_URL)
requires_ssl = parsed_db_url.hostname is not None and parsed_db_url.hostname.endswith("supabase.com")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={
        "statement_cache_size": 0,  # required for Supabase pooler compatibility
        "ssl": "require" if requires_ssl else False,
    }
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
