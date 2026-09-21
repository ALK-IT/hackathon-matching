from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import DATABASE_URL, get_session
from app.main import app

# Testy kasują i nadpisują dane (np. `DELETE FROM teams`). Od #95 backend sam
# czyta backend/.env, więc adres bazy wpisany tam "na chwilę" - np. do
# debugowania z bazą z Railway - trafiłby też do testów. Dopuszczamy tylko bazy
# lokalne: z docker compose (z komputera albo z kontenera) i tę z CI.
LOCAL_DATABASE_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres"}

if make_url(DATABASE_URL).host not in LOCAL_DATABASE_HOSTS:
    # Bez adresu w komunikacie - zawiera hasło.
    pytest.exit(
        "DATABASE_URL nie wskazuje lokalnej bazy - testy kasują dane, więc nie "
        "uruchomią się na bazie współdzielonej ani produkcyjnej. Sprawdź "
        "DATABASE_URL w zmiennych środowiskowych i w backend/.env.",
        returncode=4,
    )

# Silnik używany wyłącznie przez testy.
#
# Aplikacja trzyma pulę gotowych połączeń, co jest słuszne na produkcji, ale
# wywraca testy: TestClient uruchamia każde żądanie we własnej pętli zdarzeń,
# a połączenie asyncpg jest przypisane do pętli, w której powstało. Użycie go
# z innej pętli kończy się błędem "another operation is in progress".
#
# NullPool oznacza brak puli - każda sesja otwiera świeże połączenie i zamyka
# je po sobie, więc nic nie przechodzi między pętlami.
test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


# Podmiana zależności: endpointy dostaną sesję z silnika testowego,
# nie z produkcyjnego. Kod aplikacji pozostaje nietknięty.
app.dependency_overrides[get_session] = get_test_session
