from sqlalchemy import delete, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Submission, Team

# Klucz advisory locka serializujacego przebiegi matchowania. Dowolna stala
# 64-bitowa - wazne tylko, zeby byla jedna i ta sama we wszystkich instancjach
# backendu (lock zyje w Postgresie, wiec dziala miedzy procesami i maszynami,
# inaczej niz asyncio.Lock, ktory widzi tylko wlasny proces).
MATCHING_LOCK_KEY = 823_047_001


async def try_acquire_matching_lock(session: AsyncSession) -> bool:
    """Probuje zajac zamek przebiegu matchowania; False = inny przebieg trwa.

    pg_try_advisory_xact_lock nie czeka - odpowiada natychmiast, dzieki czemu
    rownolegle wywolanie dostaje jasna odmowe (409) zamiast wisiec w kolejce
    i po cichu nadpisac wynik poprzednika sekunde pozniej (decyzja zespolu:
    odmawiamy, nie kolejkujemy). Zamek jest transakcyjny: Postgres zwalnia go
    sam przy commit/rollback, wiec nie da sie go "zapomniec" po bledzie.
    """
    result = await session.execute(
        text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": MATCHING_LOCK_KEY}
    )
    return bool(result.scalar_one())


async def clear_teams(session: AsyncSession) -> None:
    """Kasuje dotychczasowy podział na zespoły.

    Matchowanie liczy podział od zera, więc poprzedni wynik musi zniknąć -
    inaczej zgłoszenie zostałoby przypisane do zespołu z poprzedniego
    przebiegu i "dokładnie jeden zespół" przestałoby być prawdą.

    Najpierw zdejmujemy przypisania, potem kasujemy zespoły, choć klucz obcy
    ma `ON DELETE SET NULL` i zrobiłby to sam. Powód jest po stronie sesji,
    nie bazy: obiekty `Submission` wczytane wcześniej trzymają w pamięci stary
    `team_id`, o którego wyzerowaniu przez bazę SQLAlchemy się nie dowie.
    Jawny UPDATE aktualizuje jedno i drugie, więc pamięć sesji i baza nie
    rozjeżdżają się nawet na chwilę. `ON DELETE SET NULL` zostaje jako
    zabezpieczenie dla operacji spoza tego kodu (choćby ręcznego DELETE).

    Nie zatwierdza transakcji - to należy do serwisu, który jako jedyny wie,
    czy cała operacja się powiodła. Dzięki temu nieudane matchowanie nie
    zostawia bazy bez zespołów.
    """
    await session.execute(update(Submission).values(team_id=None))
    await session.execute(delete(Team))


async def create_teams(session: AsyncSession, grouped: list[list[Submission]]) -> list[Team]:
    """Zapisuje wynik dopasowania jako nowe zespoły i zwraca je gotowe.

    Dostaje zgłoszenia pogrupowane przez algorytm (lista list) - te same
    obiekty, które wcześniej wyszły z bazy, więc przypisanie do zespołu to
    dla SQLAlchemy zwykły UPDATE ich `team_id`, bez ponownego wczytywania.

    Skład ustawiamy wprost w Pythonie (`Team(members=...)`), więc odczyt
    `team.members` przez wywołującego nie wymaga doczytania z bazy - a leniwe
    doczytanie w kodzie async kończy się wyjątkiem, nie danymi.

    `flush` wysyła INSERT-y i UPDATE-y wewnątrz transakcji; Postgres odsyła
    przy tej okazji `id` i `created_at` klauzulą RETURNING, więc zwrócone
    zespoły mają komplet pól bez dodatkowego zapytania.
    """
    teams = [Team(members=list(members)) for members in grouped]
    session.add_all(teams)
    await session.flush()
    return teams
