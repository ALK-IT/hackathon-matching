from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def ping(engine: AsyncEngine) -> None:
    """Najprostsze możliwe pytanie do bazy - sprawdza samo połączenie."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
