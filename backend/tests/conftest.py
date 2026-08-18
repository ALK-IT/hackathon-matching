from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import DATABASE_URL, get_session
from app.main import app

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
