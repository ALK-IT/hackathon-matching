import asyncio
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


# Limit PULI DO MATCHOWANIA - celowo niższy niż limit rejestracji
# (`MAX_TOTAL_SUBMISSIONS` = 3000) i celowo nie wyprowadzony z niego.
#
# To dwie różne populacje w modelu docelowym: uczestnik będzie mógł wybrać
# zespół samodzielnie, więc do algorytmu trafi tylko ta część zgłoszonych,
# która o dopasowanie prosi. 2999 zgłoszeń, z czego 1000 do zmatchowania, to
# stan normalny, a nie sprzeczność między limitami.
#
# UWAGA na dziś: wyboru zespołu jeszcze nie ma, `list_submissions` zwraca
# wszystkie wiersze, więc do czasu jego wprowadzenia zapadka mierzy komplet
# zgłoszeń i baza powyżej 2000 rekordów nie zmatchuje się wcale. Przy skali
# hackatonu ALK to stan nieosiągalny; gdy pojawi się pula "do matchowania",
# sprawdzenie ma liczyć właśnie ją, nie `len(submissions)`.
#
# Zapadka nie chroni CPU - tym zajmuje się budżet pracy w _swap_repair (patrz
# balanced.py), przy 2000 osób przebieg trwa ~1,7 s. Chodzi o rzeczy wtórne,
# przede wszystkim rozmiar odpowiedzi: JSON z pełnymi składami to przy tej
# wartości ~0,5 MB.
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

    Rzuca `MatchingInProgressError`, gdy zamek trzyma inny przebieg (#56),
    i `TooManyParticipantsError`, gdy zgłoszeń jest więcej niż
    `MAX_MATCHED_PARTICIPANTS` (#57) - router tłumaczy oba na 409.

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

    # Czyste CPU w osobnym wątku (uwaga z review #83): synchroniczne liczenie
    # w async handlerze blokowałoby cały event loop - przez czas przebiegu
    # proces nie odpowiadałby na ŻADNE żądanie, nawet zwykłe GET-y, a 409
    # "już trwa" nigdy nie miałby okazji paść w obrębie jednego workera.
    # Algorytm nie dotyka sesji bazy, więc przeniesienie do wątku jest
    # bezpieczne; zamek advisory żyje przy połączeniu i czeka na wynik.
    grouped = await asyncio.to_thread(ALGORITHMS[algorithm], submissions, team_size)

    await teams_repository.clear_teams(session)
    teams = await teams_repository.create_teams(session, grouped)
    await session.commit()

    return teams
