from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.settings import settings


def normalize_database_url(url: str) -> str:
    """Railway/Heroku itp. dają DATABASE_URL jako postgres:// albo postgresql://
    (bez sterownika) - SQLAlchemy async wymaga jawnego +asyncpg."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


# Skąd adres i co, gdy go brakuje (na Railway: błąd startu, lokalnie: baza
# z docker-compose.yml) - rozstrzyga app/settings.py.
DATABASE_URL = normalize_database_url(settings.database_url)

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Osobny silnik dla /health/ready (#91), bez puli (NullPool). Każde sprawdzenie
# otwiera świeże połączenie, więc sprawdza, czy DA SIĘ połączyć z bazą (a nie
# tylko, czy działa stare połączenie), i nie zabiera połączeń prawdziwym
# żądaniom - także wtedy, gdy przerwane sprawdzenie jeszcze sprząta po sobie
# (patrz services/health.py).
readiness_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)


class Base(DeclarativeBase):
    """Wspólna baza dla modeli ORM.

    Alembic czyta z `Base.metadata` docelowy kształt schematu, żeby
    `alembic revision --autogenerate` wiedział, co porównać z bazą.
    Modele dziedziczące po tej klasie muszą być zaimportowane, zanim
    autogenerate ruszy - inaczej ich tabele nie trafią do metadanych."""


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


def get_readiness_engine() -> AsyncEngine:
    return readiness_engine
