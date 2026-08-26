from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Submission, Team


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
