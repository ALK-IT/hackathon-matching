"""Testy sprawdzania zdrowia (#91): /health (proces żyje) i /health/ready (baza)."""

import asyncio
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.db import get_readiness_engine
from app.main import app
from app.repositories import health as health_repository
from app.services import health as health_service

client = TestClient(app)

# Port 1 na lokalnej maszynie: nikt tam nie słucha, więc połączenie jest
# odrzucane od razu - dokładnie jak przy bazie, której nie ma pod adresem.
DEAD_DATABASE_URL = "postgresql+asyncpg://hackathon:x@127.0.0.1:1/nie_ma_takiej"


@pytest.fixture
def dead_database() -> Iterator[None]:
    """Podmienia silnik sprawdzania gotowości na taki, który prowadzi do
    niedziałającej bazy - na czas jednego testu."""
    engine = create_async_engine(DEAD_DATABASE_URL, poolclass=NullPool)
    app.dependency_overrides[get_readiness_engine] = lambda: engine
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_readiness_engine, None)
        asyncio.run(engine.dispose())


def test_liveness_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_ok_when_database_answers() -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_readiness_is_503_when_database_is_down(dead_database: None) -> None:
    """Sedno #91: przy martwej bazie sprawdzenie gotowości NIE mówi "ok"."""
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}


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


def test_readiness_is_503_on_time_when_database_hangs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zamrożona baza nie może zawiesić sprawdzenia - po limicie wychodzi 503.

    Atrapa zachowuje się jak sterownik asyncpg przy zamrożonej bazie: przerwane
    zapytanie jeszcze sprząta po sobie i czeka na potwierdzenie, którego baza
    nie wyśle. Samo `asyncio.wait_for` czekało na to sprzątanie, więc 503
    przychodziło dopiero po powrocie bazy (sprawdzone na atrapie Postgresa).
    """

    async def frozen_ping(_engine: object) -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            await asyncio.sleep(3)  # "sprzątanie" po przerwaniu
            raise

    monkeypatch.setattr(health_repository, "ping", frozen_ping)
    monkeypatch.setattr(health_service, "READINESS_TIMEOUT_SECONDS", 0.05)

    started = time.monotonic()
    response = client.get("/health/ready")
    elapsed = time.monotonic() - started

    assert response.status_code == 503
    assert elapsed < 1.5


@pytest.mark.parametrize("path", ["/api/hello", "/api/db-check"])
def test_demo_endpoints_are_gone(path: str) -> None:
    """Pozostałości z pierwszego tygodnia projektu (#91) - /api/db-check
    zastępuje /health/ready, a /api/hello niczemu już nie służył."""
    assert client.get(path).status_code == 404
