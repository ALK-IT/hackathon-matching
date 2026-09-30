import asyncio
import logging
from enum import StrEnum
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import AsyncEngine

from app.repositories import health as repository

logger = logging.getLogger(__name__)

# Ile czekamy na bazę, zanim uznamy ją za niedostępną. Bez limitu sterownik
# czeka na połączenie do 60 s, a sprawdzenie zdrowia, które odpowiada po minucie,
# samo wygląda na awarię - platforma przerwie je wcześniej własnym limitem.
READINESS_TIMEOUT_SECONDS = 3.0

# Wersje schematu z plików migracji tego kodu (Dockerfile kopiuje katalog
# alembic/ do obrazu). Czytane raz, przy starcie: w trakcie działania się nie
# zmieniają. Brak katalogu zatrzymuje start - kod bez swoich migracji to błąd
# wdrożenia, a nie stan, w którym da się obsługiwać ruch.
_MIGRATIONS = ScriptDirectory(str(Path(__file__).resolve().parents[2] / "alembic"))
EXPECTED_REVISIONS = frozenset(_MIGRATIONS.get_heads())
KNOWN_REVISIONS = frozenset(migration.revision for migration in _MIGRATIONS.walk_revisions())

# Sprawdzenia przerwane po limicie, które jeszcze sprzątają po sobie. asyncio
# trzyma do zadań tylko słabe referencje - bez tego zbioru garbage collector
# mógłby zebrać takie zadanie w połowie zamykania połączenia. Przy długo
# zamrożonej bazie przybywa tu jedno zadanie (jedno połączenie) na sprawdzenie;
# znikają, gdy baza wróci albo system zerwie połączenie.
_abandoned_checks: set[asyncio.Task[set[str]]] = set()


class Readiness(StrEnum):
    READY = "ready"
    DATABASE_UNAVAILABLE = "database_unavailable"
    SCHEMA_OUTDATED = "schema_outdated"


def _abandon(check: asyncio.Task[set[str]]) -> None:
    """Przerywa sprawdzenie i NIE czeka, aż się skończy.

    Gdy baza zamarzła (połączenie otwarte, ale odpowiedzi brak), asyncpg po
    przerwaniu zapytania czeka jeszcze na jej potwierdzenie. `asyncio.wait_for`
    czekał razem z nim, więc sprawdzenie wisiało aż do powrotu bazy
    (sprawdzone na atrapie Postgresa, która milknie po połączeniu).
    """
    check.cancel()
    _abandoned_checks.add(check)
    check.add_done_callback(_forget)


def _forget(check: asyncio.Task[set[str]]) -> None:
    _abandoned_checks.discard(check)
    if not check.cancelled():
        check.exception()  # odebrany, żeby asyncio nie logowało "never retrieved"


def schema_is_current(in_database: set[str]) -> bool:
    """Czy w bazie wykonano wszystkie migracje, które zna ten kod.

    - pusto: migracji nie było wcale (np. świeża baza po przywróceniu hostingu),
    - same wersje obce temu kodowi: baza jest nowsza (migracja z innej gałęzi,
      wycofane wdrożenie). Nie mamy jak sprawdzić, czego brakuje, i nie
      blokujemy - tak samo liczą zaległe migracje Django i Rails,
    - poza tym wymagamy, żeby wersje, których kod oczekuje, były w bazie.
      Migracje mogą się rozgałęzić, więc baza trzyma wtedy kilka wersji naraz:
      obca wersja obok zaległej nie może przykryć tej zaległej, a dodatkowy
      wpis obok oczekiwanej niczego nie psuje.
    """
    if not in_database:
        return False
    if in_database.isdisjoint(KNOWN_REVISIONS):
        return True
    return EXPECTED_REVISIONS <= in_database


async def check_readiness(engine: AsyncEngine) -> Readiness:
    """Czy backend może obsługiwać ruch - nigdy wyjątek, najpóźniej po limicie.

    Łapiemy każdy wyjątek, a nie wybrane klasy: niedostępna baza objawia się
    różnie (odmowa połączenia, złe hasło, brak bazy o tej nazwie), a na każde
    z tych pytań sprawdzenie gotowości ma odpowiedzieć tak samo - "nie gotowy"
    - zamiast błędem 500. Przyczyna trafia do logu, bo z samego 503 nie da się
    jej odczytać.
    """
    check = asyncio.ensure_future(repository.schema_revisions(engine))
    try:
        done, _ = await asyncio.wait({check}, timeout=READINESS_TIMEOUT_SECONDS)
    finally:
        # Także gdy przerwano samo żądanie (klient się rozłączył, serwer się
        # zamyka) - sprawdzenie bez odbiorcy nie ma po co trwać.
        if not check.done():
            _abandon(check)

    if not done:
        logger.warning(
            "Sprawdzenie gotowości: baza nie odpowiedziała w %s s", READINESS_TIMEOUT_SECONDS
        )
        return Readiness.DATABASE_UNAVAILABLE

    error = check.exception()
    if error is not None:
        logger.warning("Sprawdzenie gotowości: baza nie odpowiada", exc_info=error)
        return Readiness.DATABASE_UNAVAILABLE

    in_database = check.result()
    if not schema_is_current(in_database):
        logger.warning(
            "Sprawdzenie gotowości: w bazie brakuje migracji (w bazie: %s, kod oczekuje: %s)"
            " - uruchom `alembic upgrade head`",
            sorted(in_database) or "brak",
            sorted(EXPECTED_REVISIONS),
        )
        return Readiness.SCHEMA_OUTDATED
    return Readiness.READY
