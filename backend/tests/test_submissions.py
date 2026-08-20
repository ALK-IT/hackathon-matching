import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import DATABASE_URL
from app.main import app

client = TestClient(app)


async def _delete_by_prefix(prefix: str) -> None:
    """Kasuje rekordy założone przez test.

    Używa własnego silnika, bo silnik aplikacji jest przypięty do pętli
    zdarzeń, w której TestClient uruchamia aplikację - sięganie po niego
    z innej pętli kończy się błędem.
    """
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM submissions WHERE email LIKE :prefix"),
            {"prefix": f"{prefix}%"},
        )
    await engine.dispose()


@pytest.fixture
def email_prefix() -> str:
    """Daje testowi unikalny przedrostek adresu i sprząta po nim na końcu.

    Unikalność jest konieczna, bo kolumna email ma ograniczenie unikalności
    - bez niej drugie uruchomienie testów wywracałoby się na duplikacie.
    """
    prefix = f"test-{uuid4().hex[:12]}-"
    yield prefix
    asyncio.run(_delete_by_prefix(prefix))


def test_create_submission_returns_201(email_prefix: str) -> None:
    response = client.post(
        "/api/submissions",
        json={
            "full_name": "Jan Kowalski",
            "email": f"{email_prefix}jan@example.com",
            "skills": "python,react",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["full_name"] == "Jan Kowalski"
    assert body["skills"] == "python,react"
    assert body["created_at"]


def test_invalid_email_returns_422() -> None:
    response = client.post(
        "/api/submissions",
        json={"full_name": "Jan Kowalski", "email": "to-nie-jest-email", "skills": "python"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("full_name", ["", "   "])
def test_empty_full_name_returns_422(full_name: str) -> None:
    """Same spacje też muszą odpaść - schemat obcina białe znaki przed walidacją."""
    response = client.post(
        "/api/submissions",
        json={"full_name": full_name, "email": "jan@example.com", "skills": "python"},
    )

    assert response.status_code == 422


def test_duplicate_email_returns_409(email_prefix: str) -> None:
    """Duplikat ma dać czytelny konflikt, a nie 500."""
    payload = {
        "full_name": "Jan Kowalski",
        "email": f"{email_prefix}duplikat@example.com",
        "skills": "python",
    }

    first = client.post("/api/submissions", json=payload)
    assert first.status_code == 201

    second = client.post("/api/submissions", json=payload)
    assert second.status_code == 409
    assert "e-mail" in second.json()["detail"]


def test_list_submissions_returns_created_submission(email_prefix: str) -> None:
    """Sprawdza, że zgłoszenie założone przez POST pojawia się na liście GET.

    Filtrujemy odpowiedź po przedrostku e-maila zamiast zakładać pustą
    tabelę - w bazie mogą być rekordy z innych testów.
    """
    email = f"{email_prefix}anna@example.com"
    created = client.post(
        "/api/submissions",
        json={"full_name": "Anna Nowak", "email": email, "skills": "python"},
    )
    assert created.status_code == 201

    response = client.get("/api/submissions")

    assert response.status_code == 200
    matching = [item for item in response.json() if item["email"] == email]
    assert len(matching) == 1
    assert matching[0]["full_name"] == "Anna Nowak"
    assert matching[0]["skills"] == "python"
