import asyncio
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import DATABASE_URL
from app.main import app

client = TestClient(app)


def payload(email: str, **overrides: Any) -> dict[str, Any]:
    """Kompletne, poprawne zgłoszenie - testy nadpisują tylko badane pole.

    Dzięki temu dołożenie kolejnego pola do modelu wymaga zmiany w jednym
    miejscu, a nie w każdym teście z osobna.
    """
    return {
        "full_name": "Jan Kowalski",
        "email": email,
        "skills": ["python", "react"],
        "experience_level": "intermediate",
        "preferred_role": "backend",
        "availability": True,
    } | overrides


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
    response = client.post("/api/submissions", json=payload(f"{email_prefix}jan@example.com"))

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["full_name"] == "Jan Kowalski"
    assert body["skills"] == ["python", "react"]
    assert body["experience_level"] == "intermediate"
    assert body["preferred_role"] == "backend"
    assert body["availability"] is True
    assert body["created_at"]


def test_invalid_email_returns_422() -> None:
    response = client.post("/api/submissions", json=payload("to-nie-jest-email"))

    assert response.status_code == 422


@pytest.mark.parametrize("full_name", ["", "   "])
def test_empty_full_name_returns_422(full_name: str) -> None:
    """Same spacje też muszą odpaść - schemat obcina białe znaki przed walidacją."""
    response = client.post("/api/submissions", json=payload("jan@example.com", full_name=full_name))

    assert response.status_code == 422


def test_duplicate_email_returns_409(email_prefix: str) -> None:
    """Duplikat ma dać czytelny konflikt, a nie 500."""
    duplicate = payload(f"{email_prefix}duplikat@example.com")

    first = client.post("/api/submissions", json=duplicate)
    assert first.status_code == 201

    second = client.post("/api/submissions", json=duplicate)
    assert second.status_code == 409
    assert "e-mail" in second.json()["detail"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("experience_level", "guru"),
        ("preferred_role", "czarodziej"),
        ("skills", []),
        ("skills", ["   "]),
        ("skills", "python,react"),
    ],
)
def test_invalid_profile_field_returns_422(field: str, value: object) -> None:
    """Pola profilu mają zamknięty zbiór wartości - wszystko poza nim to 422.

    `skills` jako tekst też musi odpaść: API przyjmuje listę, a milczące
    zaakceptowanie stringa zapisałoby całe "python,react" jako jedną
    umiejętność i po cichu zepsuło dane wejściowe dopasowania.
    """
    response = client.post("/api/submissions", json=payload("jan@example.com", **{field: value}))

    assert response.status_code == 422


def test_missing_profile_fields_return_422() -> None:
    """Nowe zgłoszenie bez profilu jest dla dopasowania bezużyteczne."""
    incomplete = payload("jan@example.com")
    del incomplete["experience_level"]
    del incomplete["preferred_role"]

    response = client.post("/api/submissions", json=incomplete)

    assert response.status_code == 422


def test_availability_defaults_to_true(email_prefix: str) -> None:
    """Brak `availability` znaczy pełną dostępność - to najczęstszy przypadek."""
    body = payload(f"{email_prefix}bez-dostepnosci@example.com")
    del body["availability"]

    response = client.post("/api/submissions", json=body)

    assert response.status_code == 201
    assert response.json()["availability"] is True


def test_skills_are_normalized(email_prefix: str) -> None:
    """Wielkość liter i powtórzenia nie mogą fałszować danych dopasowania."""
    response = client.post(
        "/api/submissions",
        json=payload(
            f"{email_prefix}umiejetnosci@example.com",
            skills=["  React ", "react", "REACT", "Python"],
        ),
    )

    assert response.status_code == 201
    assert response.json()["skills"] == ["react", "python"]


def test_list_submissions_returns_created_submission(email_prefix: str) -> None:
    """Sprawdza, że zgłoszenie założone przez POST pojawia się na liście GET.

    Filtrujemy odpowiedź po przedrostku e-maila zamiast zakładać pustą
    tabelę - w bazie mogą być rekordy z innych testów.
    """
    email = f"{email_prefix}anna@example.com"
    created = client.post(
        "/api/submissions",
        json=payload(
            email,
            full_name="Anna Nowak",
            skills=["python"],
            experience_level="advanced",
            preferred_role="design",
            availability=False,
        ),
    )
    assert created.status_code == 201

    response = client.get("/api/submissions")

    assert response.status_code == 200
    matching = [item for item in response.json() if item["email"] == email]
    assert len(matching) == 1
    assert matching[0]["full_name"] == "Anna Nowak"
    assert matching[0]["skills"] == ["python"]
    assert matching[0]["experience_level"] == "advanced"
    assert matching[0]["preferred_role"] == "design"
    assert matching[0]["availability"] is False
