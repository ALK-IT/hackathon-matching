from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Submission
from app.schemas import SubmissionCreate


async def create_submission(session: AsyncSession, data: SubmissionCreate) -> Submission:
    """Zapisuje zgłoszenie w bazie i zwraca gotowy rekord.

    Warstwa repozytorium jest jedynym miejscem w projekcie, które dotyka
    bazy (patrz CLAUDE.md: router -> service -> repository).

    Nie zatwierdza transakcji - to należy do serwisu, który wie, czy cała
    operacja się powiodła. `flush` wysyła INSERT wewnątrz transakcji, a
    Postgres odsyła przy tej okazji `id` i `created_at` klauzulą RETURNING,
    więc obiekt ma komplet pól bez dodatkowego zapytania do bazy.
    """
    submission = Submission(**data.model_dump())
    session.add(submission)
    await session.flush()
    return submission
