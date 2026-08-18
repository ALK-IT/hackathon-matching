from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Submission
from app.repositories import submissions as repository
from app.schemas import SubmissionCreate


class DuplicateEmailError(Exception):
    """Zgłoszenie z tym adresem e-mail już istnieje w bazie."""


async def submit(session: AsyncSession, payload: SubmissionCreate) -> Submission:
    """Przyjmuje zgłoszenie uczestnika i zatwierdza je w bazie.

    Duplikat e-maila wykrywamy przez próbę zapisu, a nie przez wcześniejsze
    sprawdzenie "czy istnieje". Sprawdzenie z wyprzedzeniem ma wyścig: dwa
    równoległe żądania z tym samym adresem mogą oba je przejść. Ograniczenie
    unikalności w bazie jest jedynym miejscem, które nie da się oszukać.

    Tabela `submissions` ma dokładnie jedno ograniczenie unikalności (email),
    więc IntegrityError może tu oznaczać wyłącznie duplikat adresu. Gdy dojdą
    kolejne ograniczenia, trzeba będzie rozróżniać je po nazwie.
    """
    try:
        submission = await repository.create_submission(session, payload)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateEmailError from exc
    return submission
