"""Testy sprawdzania zdrowia (#91): /health (proces żyje) i /health/ready
(baza odpowiada i ma wykonane wszystkie migracje)."""

import asyncio
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.db import DATABASE_URL, get_readiness_engine
from app.main import app
from app.repositories import health as health_repository
from app.services import health as health_service

client = TestClient(app)

# Port 1 na lokalnej maszynie: nikt tam nie słucha, więc połączenie jest
# odrzucane od razu - dokładnie jak przy bazie, której nie ma pod adresem.
DEAD_DATABASE_URL = "postgresql+asyncpg://hackathon:x@127.0.0.1:1/nie_ma_takiej"

# Baza "postgres" istnieje na każdym serwerze Postgresa i nikt nie wykonuje na
# niej naszych migracji - to prawdziwa pusta baza, jak po przywróceniu hostingu.
EMPTY_DATABASE_URL = make_url(DATABASE_URL).set(database="postgres")

READY = {"status": "ok", "database": "ok", "schema": "ok"}
DATABASE_DOWN = {"status": "unavailable", "database": "unavailable", "schema": "unknown"}
SCHEMA_OUTDATED = {"status": "unavailable", "database": "ok", "schema": "outdated"}


@pytest.fixture
def readiness_database() -> Iterator[object]:
    """Podmienia silnik sprawdzania gotowości na czas jednego testu."""
    engines = []

    def use(url: object) -> None:
        engine = create_async_engine(url, poolclass=NullPool)
        engines.append(engine)
        app.dependency_overrides[get_readiness_engine] = lambda: engine

    try:
        yield use
    finally:
        app.dependency_overrides.pop(get_readiness_engine, None)
        for engine in engines:
            asyncio.run(engine.dispose())


@pytest.fixture
def dead_database(readiness_database) -> None:
    readiness_database(DEAD_DATABASE_URL)


def schema_in_database(monkeypatch: pytest.MonkeyPatch, revisions: set[str]) -> None:
    """Udaje, że baza odpowiada i ma zapisane podane wersje schematu."""

    async def fake_schema_revisions(_engine: object) -> set[str]:
        return revisions

    monkeypatch.setattr(health_repository, "schema_revisions", fake_schema_revisions)


def test_liveness_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_ok_when_database_answers_and_is_migrated() -> None:
    """Baza testowa jest po `alembic upgrade head` (lokalnie i w CI)."""
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == READY


def test_readiness_is_503_when_database_is_down(dead_database: None) -> None:
    """Sedno #91: przy martwej bazie sprawdzenie gotowości NIE mówi "ok"."""
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == DATABASE_DOWN


def test_liveness_stays_ok_when_database_is_down(dead_database: None) -> None:
    """Podział na dwa endpointy: restart backendu nie naprawi bazy, więc
    pytanie "czy proces żyje" nie może zależeć od niej."""
    assert client.get("/health").status_code == 200
    assert client.get("/health/ready").status_code == 503


def test_readiness_does_not_leak_connection_details(dead_database: None) -> None:
    """Publiczny adres nie zdradza, gdzie stoi baza ani co odpowiedział sterownik
    - to trafia do logu serwera."""
    body = client.get("/health/ready").text

    assert "127.0.0.1" not in body
    assert "nie_ma_takiej" not in body


def test_readiness_is_503_on_empty_database(readiness_database) -> None:
    """Pusta baza (np. po przywróceniu hostingu) odpowiada na `SELECT 1`, ale nie
    ma tabel, więc lista zgłoszeń zwracałaby 500. Gotowość musi to wykryć."""
    readiness_database(EMPTY_DATABASE_URL)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == SCHEMA_OUTDATED


def test_readiness_is_503_when_migrations_are_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wdrożono kod z nową migracją, ale nikt jej nie uruchomił - baza stoi na
    starszej wersji, którą ten kod zna."""
    older = min(health_service.KNOWN_REVISIONS - health_service.EXPECTED_REVISIONS)
    schema_in_database(monkeypatch, {older})

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == SCHEMA_OUTDATED
    assert older not in response.text  # numer wersji zostaje w logu serwera


def test_readiness_ok_when_database_is_newer_than_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wersja spoza plików tego kodu to baza NOWSZA (migracja z innej gałęzi,
    wycofane wdrożenie). Niczego, co ten kod zna, nie brakuje - nie blokujemy."""
    schema_in_database(monkeypatch, {"wersja_z_innej_galezi"})

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == READY


def test_readiness_is_503_when_pending_migration_stands_next_to_unknown_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Migracje mogą się rozgałęzić i wtedy baza trzyma kilka wersji naraz.
    Obca wersja obok zaległej NIE może przykryć tej zaległej - to dokładnie ten
    brak, przed którym chroni sprawdzanie schematu."""
    older = min(health_service.KNOWN_REVISIONS - health_service.EXPECTED_REVISIONS)
    schema_in_database(monkeypatch, {older, "wersja_z_innej_galezi"})

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == SCHEMA_OUTDATED


def test_readiness_ok_when_head_is_applied_next_to_an_extra_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wersja, której kod oczekuje, JEST w bazie - dodatkowy wpis obok (po
    rozgałęzieniu migracji) niczego nie psuje."""
    older = min(health_service.KNOWN_REVISIONS - health_service.EXPECTED_REVISIONS)
    schema_in_database(monkeypatch, health_service.EXPECTED_REVISIONS | {older})

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == READY


def test_readiness_is_503_on_time_when_database_hangs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zamrożona baza nie może zawiesić sprawdzenia - po limicie wychodzi 503.

    Atrapa zachowuje się jak sterownik asyncpg przy zamrożonej bazie: przerwane
    zapytanie jeszcze sprząta po sobie i czeka na potwierdzenie, którego baza
    nie wyśle. Samo `asyncio.wait_for` czekało na to sprzątanie, więc 503
    przychodziło dopiero po powrocie bazy (sprawdzone na atrapie Postgresa).
    """

    async def frozen_query(_engine: object) -> set[str]:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            await asyncio.sleep(3)  # "sprzątanie" po przerwaniu
            raise
        return set()

    monkeypatch.setattr(health_repository, "schema_revisions", frozen_query)
    monkeypatch.setattr(health_service, "READINESS_TIMEOUT_SECONDS", 0.05)

    started = time.monotonic()
    response = client.get("/health/ready")
    elapsed = time.monotonic() - started

    assert response.status_code == 503
    assert response.json() == DATABASE_DOWN
    assert elapsed < 1.5


@pytest.mark.parametrize("path", ["/api/hello", "/api/db-check"])
def test_demo_endpoints_are_gone(path: str) -> None:
    """Pozostałości z pierwszego tygodnia projektu (#91) - /api/db-check
    zastępuje /health/ready, a /api/hello niczemu już nie służył."""
    assert client.get(path).status_code == 404
