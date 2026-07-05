from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


# SQLAlchemy 2.x style declarative base
class Base(DeclarativeBase):
    pass


# async_sessionmaker does NOT accept autocommit / autoflush — those are
# Session-level params. Pass them via the Session class or leave as defaults.
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """FastAPI dependency — yields an async DB session per request.
    
    In SIMULATION_MODE (no live PostgreSQL), yields None immediately so
    request handlers don't hang waiting for a DB connection that won't come.
    """
    if settings.SIMULATION_MODE:
        yield None
        return
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """
    Idempotent DB bootstrap:
    1. Enables pgvector and uuid-ossp extensions.
    2. Creates all declared tables if they don't already exist.

    Models are imported here (not at top level) to ensure they register
    on Base.metadata before create_all runs, and to avoid circular imports
    since models.py imports Base from this module.
    """
    import app.core.models  # noqa: F401 — triggers model registration on Base

    try:
        async with engine.begin() as conn:
            logger.info("Enabling pgvector and uuid-ossp extensions...")
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))

            logger.info("Creating database tables...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully.")
            settings.SIMULATION_MODE = False
    except Exception as e:
        logger.warning(
            "Database connection failed during boot (%s). Enabling SIMULATION_MODE fallback.",
            e
        )
        settings.SIMULATION_MODE = True

