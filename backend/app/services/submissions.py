from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Submission
from app.repositories import submissions as repository
from app.schemas import SubmissionCreate


class DuplicateEmailError(Exception):
    """Zgłoszenie z tym adresem e-mail już istnieje w bazie."""


class SubmissionLimitReachedError(Exception):
    """Baza osiągnęła limit zgłoszeń - nowych nie przyjmujemy (#57)."""


# Limit wyprowadzony z pomiarów, nie z powietrza: największe realne hackathony
# to 1-2 tys. osób, a przy 3 tys. rekordów niepaginowany GET /api/submissions
# zwraca ~0,6-0,7 MB JSON-u - dziesięciokrotnie więcej byłoby już problemem.
# Limit ma zatrzymać MASOWE fałszywe zgłoszenia (wektor DoS z #57), nie
# 3001. uczestnika. Sprawdzenie licznikiem bez locka jest ŚWIADOMIE miękkie:
# w oknie count->insert równoległe żądania mogą przepuścić ponad limit tyle
# rekordów, ile klient zdąży wystrzelić naraz (ogranicza to pula połączeń,
# nie ta stała). To nie jest twarda gwarancja - twardym sufitem kosztu CPU
# jest MAX_MATCHED_PARTICIPANTS i budżet pracy w warstwach 2-3.
MAX_TOTAL_SUBMISSIONS = 3000


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
    if await repository.count_submissions(session) >= MAX_TOTAL_SUBMISSIONS:
        raise SubmissionLimitReachedError

    try:
        submission = await repository.create_submission(session, payload)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateEmailError from exc
    return submission


async def get_all(session: AsyncSession) -> list[Submission]:
    """Zwraca wszystkie zgłoszenia do wyświetlenia na liście."""
    return await repository.list_submissions(session)
