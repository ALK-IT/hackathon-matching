"""Skrypt seedujący dane deweloperskie (#96).

Nacisk na dwie rzeczy: że wygenerowane dane naprawdę nadają się do testowania
matchowania (różnorodne, deterministyczne, poprawne wobec walidacji API) oraz
że skrypt nie potrafi skasować czegoś, czego nie powinien.
"""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.db import DATABASE_URL
from app.enums import ExperienceLevel, PreferredRole
from scripts import seed

# Wzorzec adresów seeda wyprowadzony ze skryptu, a nie przepisany: literał
# w testach przestałby pasować przy zmianie domeny i sprzątanie po cichu
# zaczęłoby nie działać.
WZORZEC = {"p": f"%@{seed.SEED_EMAIL_DOMAIN}"}


@pytest.fixture
def sprzatanie_seeda() -> None:
    """Kasuje rekordy seeda po teście - mają stałe adresy, więc da się je wskazać."""
    yield

    async def cleanup() -> None:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE submissions SET team_id=NULL WHERE email LIKE :p"), WZORZEC
            )
            await conn.execute(text("DELETE FROM submissions WHERE email LIKE :p"), WZORZEC)
        await engine.dispose()

    asyncio.run(cleanup())


# --- generowanie danych (bez bazy) ---


def test_generuje_zadana_liczbe_zgloszen() -> None:
    assert len(seed._build_submissions(25)) == 25
    assert len(seed._build_submissions(7)) == 7


def test_dane_sa_deterministyczne() -> None:
    """Dwa uruchomienia dają ten sam zestaw.

    To nie jest kaprys: bez tego nie da się powiedzieć, czy zmiana wyniku
    matchowania bierze się ze zmiany w algorytmie, czy z innych danych
    wejściowych.
    """
    pierwsze = seed._build_submissions(10)
    drugie = seed._build_submissions(10)

    assert [s.model_dump() for s in pierwsze] == [s.model_dump() for s in drugie]


def test_adresy_sa_unikalne() -> None:
    """Duplikat wywróciłby zapis na ograniczeniu unikalności."""
    adresy = [s.email for s in seed._build_submissions(30)]

    assert len(set(adresy)) == 30


def test_dane_sa_zroznicowane_pod_katem_matchowania() -> None:
    """Seed ma dawać algorytmowi na czym pracować.

    Zestaw z jedną rolą albo samymi dostępnymi osobami przeszedłby przez
    matchowanie bez trudu i niczego by nie pokazał - a to jedyny powód,
    dla którego ten skrypt istnieje.
    """
    zgloszenia = seed._build_submissions(25)

    assert {s.preferred_role for s in zgloszenia} == set(PreferredRole)
    assert {s.experience_level for s in zgloszenia} == set(ExperienceLevel)
    assert {s.availability for s in zgloszenia} == {True, False}
    # Umiejętności muszą się przecinać między osobami, inaczej składnik funkcji
    # celu karzący powtórzenia byłby zawsze zerowy.
    wszystkie = [skill for s in zgloszenia for skill in s.skills]
    assert len(wszystkie) > len(set(wszystkie))


# --- zapora przed kasowaniem nie tej bazy, co trzeba ---


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "postgres"])
def test_lokalna_baza_przechodzi(monkeypatch: pytest.MonkeyPatch, host: str) -> None:
    monkeypatch.setattr(seed, "DATABASE_URL", f"postgresql+asyncpg://u:p@{host}:5432/db")

    seed._require_local_database()


@pytest.mark.parametrize("host", ["prod.railway.app", "10.0.0.5", "baza.example.com"])
def test_zdalna_baza_jest_odrzucana(monkeypatch: pytest.MonkeyPatch, host: str) -> None:
    """Skrypt KASUJE dane, a DATABASE_URL bywa przestawiony na zdalną bazę.

    Bez tej zapory jedno `--clear` przy złym ustawieniu czyści zgłoszenia
    z produkcji - i nie ma ich skąd odtworzyć.
    """
    monkeypatch.setattr(seed, "DATABASE_URL", f"postgresql+asyncpg://u:p@{host}:5432/db")

    with pytest.raises(SystemExit):
        seed._require_local_database()


# --- pełny przebieg na bazie ---


def test_pelny_przebieg_kasuje_i_zapisuje(sprzatanie_seeda: None) -> None:
    """Regresja na błąd, który miał ten skrypt: dwa osobne `asyncio.run`.

    Silnik aplikacji trzyma pulę połączeń przypiętych do pętli zdarzeń, więc
    kasowanie w jednej pętli i zapis w drugiej kończyło się `RuntimeError`
    PO skasowaniu danych, a PRZED ich wstawieniem. Ten test przechodzi tylko
    wtedy, gdy obie operacje dzielą jedną pętlę.
    """
    asyncio.run(seed._run(count=5, clear=True))

    async def policz() -> int:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT count(*) FROM submissions WHERE email LIKE :p"), WZORZEC
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    assert asyncio.run(policz()) == 5


def test_clear_nie_rusza_rekordow_spoza_seeda() -> None:
    """Regresja na uwagę z review #128: `--clear` kasował CAŁE tabele.

    Wcześniej `_clear()` robiło `delete(Submission)` i `delete(Team)` bez
    żadnego filtra. Na współdzielonej lokalnej bazie z trwałym wolumenem
    oznaczało to, że samo uruchomienie `pytest` - przez ten plik - kasowało
    prawdziwe zgłoszenia wpisane ręcznie przez dewelopera. Po cichu i bez
    możliwości odtworzenia.

    Scenariusz sprawdza wszystkie trzy kroki `_clear()` naraz: obcy rekord
    ma przetrwać, ma zachować przypisanie do zespołu, a jego zespół nie może
    paść przy sprzątaniu zespołów pustych.
    """
    obcy_email = f"nie-seed-{uuid4().hex[:8]}@example.com"

    async def przygotuj() -> int:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                team_id = (
                    await conn.execute(text("INSERT INTO teams DEFAULT VALUES RETURNING id"))
                ).scalar_one()
                await conn.execute(
                    text(
                        "INSERT INTO submissions (full_name, email, skills, availability, team_id) "
                        "VALUES ('Prawdziwy Uczestnik', :e, ARRAY['python'], true, :t)"
                    ),
                    {"e": obcy_email, "t": team_id},
                )
                return int(team_id)
        finally:
            await engine.dispose()

    async def sprawdz(team_id: int) -> tuple[int, int]:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                zgloszen = await conn.execute(
                    text("SELECT count(*) FROM submissions WHERE email = :e AND team_id = :t"),
                    {"e": obcy_email, "t": team_id},
                )
                zespolow = await conn.execute(
                    text("SELECT count(*) FROM teams WHERE id = :t"), {"t": team_id}
                )
                return int(zgloszen.scalar_one()), int(zespolow.scalar_one())
        finally:
            await engine.dispose()

    async def posprzataj(team_id: int) -> None:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM submissions WHERE email = :e OR email LIKE :p"),
                    {"e": obcy_email, **WZORZEC},
                )
                await conn.execute(text("DELETE FROM teams WHERE id = :t"), {"t": team_id})
        finally:
            await engine.dispose()

    team_id = asyncio.run(przygotuj())
    try:
        asyncio.run(seed._run(count=3, clear=True))

        zgloszen, zespolow = asyncio.run(sprawdz(team_id))
        assert zgloszen == 1, "obce zgłoszenie zostało skasowane przez --clear"
        assert zespolow == 1, "zespół obcego zgłoszenia został skasowany przez --clear"
    finally:
        asyncio.run(posprzataj(team_id))


def test_adres_zaczynajacy_sie_od_seed_nie_jest_kasowany() -> None:
    """Powód zmiany znacznika z prefiksu na domenę.

    Filtr `email LIKE 'seed-%'` kasowałby prawdziwe zgłoszenie o adresie
    w rodzaju "seed-fund@alk.edu.pl" - prefiks bywa zwyczajnym fragmentem
    adresu. Domena `seed.example.com` jest zarezerwowana normą RFC 2606:
    nikt nie może jej zarejestrować i nie dochodzi tam poczta, więc żaden
    uczestnik nie ma jak się nią zgłosić.
    """
    pulapka = f"seed-fundusz-{uuid4().hex[:8]}@alk.edu.pl"

    async def wstaw() -> None:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO submissions (full_name, email, skills, availability) "
                        "VALUES ('Prawdziwy Uczestnik', :e, ARRAY['python'], true)"
                    ),
                    {"e": pulapka},
                )
        finally:
            await engine.dispose()

    async def czy_istnieje() -> int:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT count(*) FROM submissions WHERE email = :e"), {"e": pulapka}
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    async def posprzataj() -> None:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM submissions WHERE email = :e OR email LIKE :p"),
                    {"e": pulapka, **WZORZEC},
                )
        finally:
            await engine.dispose()

    asyncio.run(wstaw())
    try:
        asyncio.run(seed._run(count=3, clear=True))

        assert asyncio.run(czy_istnieje()) == 1, "adres zaczynający się od 'seed-' został skasowany"
    finally:
        asyncio.run(posprzataj())


def test_pusty_zespol_bez_seeda_zostaje_nietkniety() -> None:
    """`--clear` nie sprząta cudzych pustych zespołów.

    Pusty zespół mógł powstać nie przez ten skrypt i może być komuś potrzebny -
    skrypt seedujący nie ma mandatu, żeby o tym decydować. Rusza wyłącznie
    zespoły, w których faktycznie siedziały jego własne rekordy.

    Scenariusz musi zawierać zespół Z REKORDEM SEEDA, inaczej `zespoly_seeda`
    wychodzi puste, cały blok kasujący się nie wykonuje i test przechodziłby
    także przy zepsutym kodzie. (Pierwsza wersja tego testu miała dokładnie
    tę wadę - wyszło przy sprawdzeniu mutacyjnym.)
    """

    async def przygotuj() -> tuple[int, int]:
        """Zwraca (pusty zespół obcy, zespół z rekordem seeda)."""
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                obcy = (
                    await conn.execute(text("INSERT INTO teams DEFAULT VALUES RETURNING id"))
                ).scalar_one()
                poseedowy = (
                    await conn.execute(text("INSERT INTO teams DEFAULT VALUES RETURNING id"))
                ).scalar_one()
                await conn.execute(
                    text("UPDATE submissions SET team_id = :t WHERE email LIKE :p"),
                    {"t": poseedowy, **WZORZEC},
                )
                return int(obcy), int(poseedowy)
        finally:
            await engine.dispose()

    async def ktore_istnieja(ids: tuple[int, int]) -> set[int]:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT id FROM teams WHERE id = ANY(:ids)"), {"ids": list(ids)}
                )
                return {row[0] for row in result}
        finally:
            await engine.dispose()

    async def posprzataj(ids: tuple[int, int]) -> None:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("DELETE FROM submissions WHERE email LIKE :p"), WZORZEC)
                await conn.execute(
                    text("DELETE FROM teams WHERE id = ANY(:ids)"), {"ids": list(ids)}
                )
        finally:
            await engine.dispose()

    # Najpierw dane seeda, potem przypisanie ich do zespołu - dopiero wtedy
    # `--clear` ma powód, żeby w ogóle sięgnąć do tabeli zespołów.
    asyncio.run(seed._run(count=3, clear=True))
    obcy, poseedowy = asyncio.run(przygotuj())

    try:
        asyncio.run(seed._run(count=3, clear=True))

        istniejace = asyncio.run(ktore_istnieja((obcy, poseedowy)))
        assert obcy in istniejace, "pusty zespół spoza seeda został skasowany"
        assert poseedowy not in istniejace, "zespół po rekordach seeda powinien zniknąć"
    finally:
        asyncio.run(posprzataj((obcy, poseedowy)))
