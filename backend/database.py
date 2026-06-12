"""ASSO Database Setup — SQLAlchemy async engine with SQLite/MySQL support"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from config import Config

engine = create_async_engine(
    Config.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables"""
    from models import Service, Metric, Prediction, Action, ComparisonRun  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency injection for FastAPI"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
