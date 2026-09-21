from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def schema_revisions(engine: AsyncEngine) -> set[str]:
    """Wersje schematu, które alembic zapisał w bazie (tabela `alembic_version`).

    Pusty zbiór, gdy migracji nie wykonano ani razu - wtedy tej tabeli nie ma.
    Udane zapytanie przy okazji potwierdza, że baza w ogóle odpowiada.
    """
    async with engine.connect() as connection:
        # Najpierw pytamy, czy tabela istnieje: pusta baza to tu zwykła
        # odpowiedź, a nie błąd zapytania.
        exists = await connection.scalar(text("SELECT to_regclass('alembic_version') IS NOT NULL"))
        if not exists:
            return set()
        return set(await connection.scalars(text("SELECT version_num FROM alembic_version")))
