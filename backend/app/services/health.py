import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncEngine

from app.repositories import health as repository

logger = logging.getLogger(__name__)

# Ile czekamy na bazę, zanim uznamy ją za niedostępną. Bez limitu sterownik
# czeka na połączenie do 60 s, a sprawdzenie zdrowia, które odpowiada po minucie,
# samo wygląda na awarię - platforma przerwie je wcześniej własnym limitem.
READINESS_TIMEOUT_SECONDS = 3.0

# Sprawdzenia przerwane po limicie, które jeszcze sprzątają po sobie. asyncio
# trzyma do zadań tylko słabe referencje - bez tego zbioru garbage collector
# mógłby zebrać takie zadanie w połowie zamykania połączenia. Przy długo
# zamrożonej bazie przybywa tu jedno zadanie (jedno połączenie) na sprawdzenie;
# znikają, gdy baza wróci albo system zerwie połączenie.
_abandoned_pings: set[asyncio.Task[None]] = set()


def _abandon(ping: asyncio.Task[None]) -> None:
    """Przerywa sprawdzenie i NIE czeka, aż się skończy.

    Gdy baza zamarzła (połączenie otwarte, ale odpowiedzi brak), asyncpg po
    przerwaniu zapytania czeka jeszcze na jej potwierdzenie. `asyncio.wait_for`
    czekał razem z nim, więc sprawdzenie wisiało aż do powrotu bazy
    (sprawdzone na atrapie Postgresa, która milknie po połączeniu).
    """
    ping.cancel()
    _abandoned_pings.add(ping)
    ping.add_done_callback(_forget)


def _forget(ping: asyncio.Task[None]) -> None:
    _abandoned_pings.discard(ping)
    if not ping.cancelled():
        ping.exception()  # odebrany, żeby asyncio nie logowało "never retrieved"


async def database_ready(engine: AsyncEngine) -> bool:
    """Czy baza odpowiada - True/False, nigdy wyjątek, najpóźniej po limicie.

    Łapiemy każdy wyjątek, a nie wybrane klasy: niedostępna baza objawia się
    różnie (odmowa połączenia, złe hasło, brak bazy o tej nazwie), a na każde
    z tych pytań sprawdzenie gotowości ma odpowiedzieć tak samo - "nie gotowy"
    - zamiast błędem 500. Przyczyna trafia do logu, bo z samego 503 nie da się
    jej odczytać.
    """
    ping = asyncio.ensure_future(repository.ping(engine))
    try:
        done, _ = await asyncio.wait({ping}, timeout=READINESS_TIMEOUT_SECONDS)
    finally:
        # Także gdy przerwano samo żądanie (klient się rozłączył, serwer się
        # zamyka) - sprawdzenie bez odbiorcy nie ma po co trwać.
        if not ping.done():
            _abandon(ping)

    if not done:
        logger.warning(
            "Sprawdzenie gotowości: baza nie odpowiedziała w %s s", READINESS_TIMEOUT_SECONDS
        )
        return False

    error = ping.exception()
    if error is not None:
        logger.warning("Sprawdzenie gotowości: baza nie odpowiada", exc_info=error)
        return False
    return True
