from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MatchingAlgorithm
from app.matching.balanced import balanced_teams
from app.matching.baseline import random_teams
from app.models import Submission, Team
from app.repositories import submissions as submissions_repository
from app.repositories import teams as teams_repository


class NoSubmissionsError(Exception):
    """W bazie nie ma żadnego zgłoszenia, więc nie ma z czego układać zespołów."""


class MatchingInProgressError(Exception):
    """Inny przebieg matchowania właśnie trwa - równoległy jest odrzucany (#56)."""


class TooManyParticipantsError(Exception):
    """Zgłoszeń jest więcej, niż matchowanie sensownie obsłuży (#57)."""


# Limit wejścia do algorytmu. CPU pilnuje budżet pracy w _swap_repair (patrz
# balanced.py), więc ta stała chroni tylko rzeczy wtórne: odpowiedź JSON
# z pełnymi składami przy 2000 osób to już ~0,5 MB. Żaden realny hackathon
# w to nie uderzy - limit istnieje na wypadek masowych fałszywych zgłoszeń,
# które przecisnęły się mimo limitu w POST /api/submissions.
MAX_MATCHED_PARTICIPANTS = 2000


# Mapa "nazwa z API -> funkcja". Dzięki niej router nie musi wiedzieć nic
# o modułach `app/matching/`, a dołożenie kolejnego wariantu algorytmu to
# jeden wpis tutaj i jedna wartość w `MatchingAlgorithm`.
#
# Nazwy są kluczami enuma, nie dowolnym tekstem - żadne wejście od klienta
# nie ma prawa wskazać funkcji spoza tego słownika (patrz SECURITY.md).
ALGORITHMS: dict[MatchingAlgorithm, Callable[[list[Submission], int], list[list[Submission]]]] = {
    MatchingAlgorithm.BALANCED: balanced_teams,
    MatchingAlgorithm.RANDOM: random_teams,
}


async def run_matching(
    session: AsyncSession,
    team_size: int,
    algorithm: MatchingAlgorithm = MatchingAlgorithm.BALANCED,
) -> list[Team]:
    """Układa wszystkie zgłoszenia w zespoły i zapisuje wynik.

    Warstwa, która spina czysty algorytm z bazą: sama nie liczy podziału
    (to `app/matching/`) i sama nie wykonuje zapytań (to repozytoria) -
    decyduje o kolejności kroków i o tym, kiedy transakcja jest gotowa.

    Każde uruchomienie **zastępuje** poprzedni podział, a nie dokłada się do
    niego. Wynik matchowania jest jedną odpowiedzią na pytanie "jak dzielimy
    tych ludzi", a nie historią prób; trzymanie kilku podziałów naraz
    złamałoby regułę "jedno zgłoszenie w dokładnie jednym zespole" i wymagało
    dodatkowej decyzji, który z nich jest tym obowiązującym.

    Kasowanie i zapis dzielą jedną transakcję, zatwierdzaną dopiero na końcu.
    To nie jest szczegół: gdyby algorytm albo zapis się wywrócił po
    zatwierdzonym kasowaniu, zostalibyśmy z bazą bez zespołów i bez wyniku.
    Przy jednej transakcji nieudany przebieg zostawia poprzedni podział
    nietknięty.

    Rzuca `NoSubmissionsError`, gdy nie ma żadnego zgłoszenia - pusta lista
    zespołów byłaby poprawną odpowiedzią na bezsensowne pytanie i wyglądała
    dla klienta jak awaria algorytmu, a nie jak pusta baza.

    Rzuca `ValueError` przy `team_size` mniejszym niż 1 (walidacja w
    `team_sizes`); router odsiewa takie wartości wcześniej, ale funkcja jest
    wywoływalna także poza HTTP i nie zakłada, że ktoś ją przed tym ochronił.
    """
    # Zamek przed czymkolwiek innym: dwa równoległe przebiegi czytające te
    # same zgłoszenia i niezależnie kasujące/budujące zespoły mogą zostawić
    # niespójny stan (#56). Odmowa zamiast kolejkowania - patrz docstring
    # try_acquire_matching_lock.
    if not await teams_repository.try_acquire_matching_lock(session):
        raise MatchingInProgressError

    submissions = await submissions_repository.list_submissions(session)
    if not submissions:
        raise NoSubmissionsError
    if len(submissions) > MAX_MATCHED_PARTICIPANTS:
        raise TooManyParticipantsError

    grouped = ALGORITHMS[algorithm](submissions, team_size)

    await teams_repository.clear_teams(session)
    teams = await teams_repository.create_teams(session, grouped)
    await session.commit()

    return teams
