import asyncio
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import DATABASE_URL
from app.main import app
from app.services import matching as service

client = TestClient(app)

# Profile uczestników dobrane tak, żeby było co balansować: trzy poziomy
# doświadczenia i cztery role. Test nie sprawdza jakości podziału (od tego są
# testy samego algorytmu) - potrzebuje jednak danych, na których algorytm robi
# coś więcej niż pocięcie listy po kolei.
PROFILES: list[tuple[str, str]] = [
    ("advanced", "backend"),
    ("intermediate", "frontend"),
    ("beginner", "design"),
    ("advanced", "frontend"),
    ("intermediate", "backend"),
    ("beginner", "pm"),
    ("intermediate", "design"),
]


def payload(email: str, experience_level: str, preferred_role: str) -> dict[str, Any]:
    return {
        "full_name": "Uczestnik Testowy",
        "email": email,
        "skills": ["python", preferred_role],
        "experience_level": experience_level,
        "preferred_role": preferred_role,
        "availability": True,
    }


async def _cleanup(prefix: str) -> None:
    """Sprząta po teście: zgłoszenia założone przez ten test i wszystkie zespoły.

    Własny silnik, bo silnik aplikacji jest przypięty do pętli zdarzeń, w której
    TestClient uruchamia aplikację (szczegóły w tests/conftest.py).

    Zespoły kasujemy w całości, nie tylko "swoje": zespół nie ma po czym poznać,
    z którego testu pochodzi, a i tak każde matchowanie zastępuje poprzedni
    podział - to wynik do przeliczenia, nie dane, które ktoś mógłby stracić.
    Zgłoszeń dotyczy odwrotna zasada, więc te kasujemy wyłącznie po przedrostku.
    """
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM submissions WHERE email LIKE :prefix"),
            {"prefix": f"{prefix}%"},
        )
        await conn.execute(text("DELETE FROM teams"))
    await engine.dispose()


async def _team_ids_for(prefix: str) -> list[int | None]:
    """Czyta z bazy przypisania do zespołów - z pominięciem API.

    Odpowiedź endpointu pokazuje, co zwrócił serwis; dopiero osobny odczyt
    pokazuje, co naprawdę zostało zatwierdzone w bazie. Bez tego test przeszedłby
    także wtedy, gdyby zabrakło `commit`.
    """
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT team_id FROM submissions WHERE email LIKE :prefix ORDER BY id"),
            {"prefix": f"{prefix}%"},
        )
        team_ids = [row[0] for row in result]
    await engine.dispose()
    return team_ids


@pytest.fixture
def participants() -> str:
    """Wrzuca do bazy komplet zgłoszeń i oddaje ich wspólny przedrostek adresu.

    Przedrostek jest unikalny na uruchomienie, bo kolumna e-mail ma ograniczenie
    unikalności - bez tego drugie odpalenie testów wywracałoby się na duplikacie.
    """
    prefix = f"match-{uuid4().hex[:12]}-"

    for index, (experience_level, preferred_role) in enumerate(PROFILES):
        response = client.post(
            "/api/submissions",
            json=payload(f"{prefix}{index}@example.com", experience_level, preferred_role),
        )
        assert response.status_code == 201

    yield prefix

    asyncio.run(_cleanup(prefix))


def emails_in(teams: list[dict[str, Any]]) -> list[str]:
    return [member["email"] for team in teams for member in team["members"]]


def test_match_returns_201_with_teams(participants: str) -> None:
    """Podstawowy przepływ z issue: zapełniona baza -> zespoły w odpowiedzi."""
    response = client.post("/api/match", params={"team_size": 3})

    assert response.status_code == 201
    teams = response.json()
    assert teams

    for team in teams:
        assert team["id"] > 0
        assert team["created_at"]
        # Gwarancje algorytmu, których musi dotrzymać też droga przez API:
        # żaden zespół nie jest pusty i żaden nie przekracza limitu.
        assert 1 <= len(team["members"]) <= 3
    # Skład to pełne zgłoszenia, nie same identyfikatory - front ma z czego
    # narysować listę bez dodatkowych żądań. Sprawdzamy to na własnych
    # uczestnikach: w bazie mogą leżeć zgłoszenia z innych testów albo dodane
    # ręcznie i one też wchodzą do podziału.
    ours = [
        member
        for team in teams
        for member in team["members"]
        if member["email"].startswith(participants)
    ]
    assert len(ours) == len(PROFILES)
    for member in ours:
        assert member["full_name"] == "Uczestnik Testowy"
        assert member["skills"]
        assert member["experience_level"]
        assert member["preferred_role"]


def test_every_participant_lands_in_exactly_one_team(participants: str) -> None:
    """Kryterium akceptacji: każde zgłoszenie w dokładnie jednym zespole.

    Sprawdzamy tylko własne adresy, a nie całą zawartość odpowiedzi: w bazie
    mogą być zgłoszenia z innych testów i one też wejdą do podziału.
    """
    response = client.post("/api/match", params={"team_size": 3})

    assert response.status_code == 201
    ours = [email for email in emails_in(response.json()) if email.startswith(participants)]
    assert sorted(ours) == sorted(f"{participants}{index}@example.com" for index in range(7))


def test_match_covers_all_submissions_in_database(participants: str) -> None:
    """Nikt nie zostaje poza podziałem - także zgłoszenia spoza tego testu."""
    all_submissions = client.get("/api/submissions").json()

    response = client.post("/api/match", params={"team_size": 4})

    assert response.status_code == 201
    assert len(emails_in(response.json())) == len(all_submissions)


def test_assignment_is_persisted(participants: str) -> None:
    """Wynik ma zostać w bazie, nie tylko w odpowiedzi HTTP."""
    response = client.post("/api/match", params={"team_size": 3})
    returned_ids = {team["id"] for team in response.json()}

    stored = asyncio.run(_team_ids_for(participants))

    assert len(stored) == len(PROFILES)
    assert all(team_id is not None for team_id in stored)
    assert set(stored) <= returned_ids


def test_rerun_replaces_previous_teams(participants: str) -> None:
    """Drugie uruchomienie zastępuje podział, a nie dokłada się do niego.

    Bez kasowania poprzedniego wyniku zgłoszenie zostałoby w starym zespole
    i "dokładnie jeden zespół" przestałoby być prawdą.
    """
    first = client.post("/api/match", params={"team_size": 3})
    assert first.status_code == 201
    first_ids = {team["id"] for team in first.json()}

    second = client.post("/api/match", params={"team_size": 3})
    assert second.status_code == 201
    second_ids = {team["id"] for team in second.json()}

    assert not first_ids & second_ids

    stored = asyncio.run(_team_ids_for(participants))
    assert set(stored) <= second_ids


def test_random_algorithm_is_available(participants: str) -> None:
    """`random` zostaje w API jako punkt odniesienia dla `balanced`."""
    response = client.post("/api/match", params={"team_size": 3, "algorithm": "random"})

    assert response.status_code == 201
    ours = [email for email in emails_in(response.json()) if email.startswith(participants)]
    assert len(ours) == len(PROFILES)


def test_default_team_size_is_used(participants: str) -> None:
    """Wywołanie bez parametrów ma działać - domyślny limit to 4."""
    response = client.post("/api/match")

    assert response.status_code == 201
    assert all(len(team["members"]) <= 4 for team in response.json())


@pytest.mark.parametrize("team_size", [0, -1, 21, "cztery"])
def test_invalid_team_size_returns_422(team_size: object) -> None:
    """Rozmiar spoza zakresu odsiewa walidacja, a nie algorytm w środku."""
    response = client.post("/api/match", params={"team_size": team_size})

    assert response.status_code == 422


def test_unknown_algorithm_returns_422() -> None:
    """Nazwa algorytmu przychodzi z zewnątrz i wskazuje funkcję do uruchomienia.

    Zbiór jest zamknięty, więc cokolwiek spoza niego musi odpaść na walidacji -
    nigdy nie trafić do wyboru w `ALGORITHMS`.
    """
    response = client.post("/api/match", params={"algorithm": "sekretny"})

    assert response.status_code == 422


def test_validation_message_is_in_polish() -> None:
    """Komunikat błędu trafia do interfejsu, więc musi być po polsku."""
    response = client.post("/api/match", params={"team_size": 0})

    messages = [error["msg"] for error in response.json()["detail"]]
    assert messages == ["Rozmiar zespołu musi być liczbą od 1 do 20."]


def test_empty_database_returns_409(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pusta baza to 409, a nie 500 ani puste 201.

    Podstawiamy puste repozytorium zamiast czyścić tabelę: kasowanie wszystkich
    zgłoszeń zniszczyłoby dane innych testów i lokalnej bazy deweloperskiej,
    a sprawdzamy tu zachowanie serwisu, nie zawartość bazy.
    """

    async def no_submissions(session: Any) -> list[Any]:
        return []

    monkeypatch.setattr(service.submissions_repository, "list_submissions", no_submissions)

    response = client.post("/api/match")

    assert response.status_code == 409
    assert "Brak zgłoszeń" in response.json()["detail"]
