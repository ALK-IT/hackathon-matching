import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def normalize_database_url(url: str) -> str:
    """Railway/Heroku itp. dają DATABASE_URL jako postgres:// albo postgresql://
    (bez sterownika) - SQLAlchemy async wymaga jawnego +asyncpg."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


DATABASE_URL = normalize_database_url(
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://hackathon:hackathon@localhost:5432/hackathon_matching",
    )
)

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
