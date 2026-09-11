from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Submission
from app.repositories import submissions as repository
from app.schemas import SubmissionCreate


class DuplicateEmailError(Exception):
    """Zgłoszenie z tym adresem e-mail już istnieje w bazie."""


class SubmissionLimitReachedError(Exception):
    """Baza osiągnęła limit zgłoszeń - nowych nie przyjmujemy (#57)."""


# Nazwa ograniczenia unikalności e-maila. Postgres nadaje ją sam, według wzorca
# "<tabela>_<kolumna>_key", bo w modelu deklarujemy tylko `unique=True` bez
# własnej nazwy. Stała bywa więc zależna od konwencji, której nikt nie zapisał
# wprost - dlatego osobny test porównuje ją z tym, co naprawdę siedzi w bazie.
EMAIL_UNIQUE_CONSTRAINT = "submissions_email_key"


def _violated_constraint(error: IntegrityError) -> str | None:
    """Wyciąga nazwę naruszonego ograniczenia z wyjątku SQLAlchemy.

    Droga jest dłuższa, niż się wydaje. `error.orig` to opakowanie SQLAlchemy
    nad sterownikiem i NIE ma ani `.diag` (to składnia psycopg2), ani
    `.constraint_name`. Prawdziwy wyjątek asyncpg - `UniqueViolationError`
    albo `CheckViolationError` - siedzi dopiero w jego `__cause__` i dopiero
    on niesie nazwę.

    `getattr` z wartością domyślną zamiast bezpośredniego dostępu, bo ta
    ścieżka zależy od wewnętrznej budowy sterownika. Gdyby kolejna wersja
    asyncpg albo SQLAlchemy ją zmieniła, dostaniemy `None` i zachowamy się
    jak przy nieznanym ograniczeniu - czyli przepuścimy błąd wyżej - zamiast
    wywrócić się na `AttributeError` w obsłudze błędu.
    """
    cause = getattr(error.orig, "__cause__", None)
    name = getattr(cause, "constraint_name", None)
    return name if isinstance(name, str) else None


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

    Na duplikat adresu tłumaczymy wyłącznie naruszenie ograniczenia
    unikalności e-maila, rozpoznane po nazwie (#100). Wcześniej każdy
    `IntegrityError` był duplikatem, co działało dopóty, dopóki przy tym
    zapisie mogło zadziałać tylko jedno ograniczenie. Tabela ma ich dziś
    sześć, a dołożenie kolejnego zamieniłoby prawdziwy błąd w komunikat
    "e-mail już istnieje" - mylący dla użytkownika i niewidoczny dla nas.

    Nieznane ograniczenie przepuszczamy wyżej, czyli kończy się odpowiedzią
    500 i śladem w logu serwera. To właściwe zachowanie: jeśli baza odrzuca
    zapis z powodu, którego nie przewidzieliśmy, jest to błąd po naszej
    stronie, a nie coś, co uczestnik może poprawić w formularzu.
    """
    if await repository.count_submissions(session) >= MAX_TOTAL_SUBMISSIONS:
        raise SubmissionLimitReachedError

    try:
        submission = await repository.create_submission(session, payload)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if _violated_constraint(exc) == EMAIL_UNIQUE_CONSTRAINT:
            raise DuplicateEmailError from exc
        raise
    return submission


async def get_all(session: AsyncSession) -> list[Submission]:
    """Zwraca wszystkie zgłoszenia do wyświetlenia na liście."""
    return await repository.list_submissions(session)
