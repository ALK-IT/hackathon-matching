"""Testy zabezpieczeń matchowania: lock (#56), limity i budżet pracy (#57)."""

import asyncio
import time
from dataclasses import dataclass, field
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import app.matching.balanced as balanced_module
import app.services.matching as matching_service
import app.services.submissions as submissions_service
from app.db import DATABASE_URL
from app.enums import ExperienceLevel, PreferredRole
from app.main import app
from app.matching.baseline import team_sizes
from app.repositories.teams import MATCHING_LOCK_KEY

client = TestClient(app)


def _payload(prefix: str, index: int) -> dict:
    return {
        "full_name": f"Uczestnik {index}",
        "email": f"{prefix}{index}@example.com",
        "skills": ["python"],
        "experience_level": "intermediate",
        "preferred_role": "backend",
        "availability": True,
    }


@dataclass
class Person:
    """Uczestnik dla testów samego algorytmu - bez bazy i bez HTTP.

    Algorytm czyta profil przez protokół `Participant`, więc naprawę wymianami
    da się sprawdzić na zwykłym dataclassie, bez zapisanych zgłoszeń.
    """

    name: str
    experience_level: ExperienceLevel | None
    preferred_role: PreferredRole | None
    skills: list[str] = field(default_factory=list)


def _people(count: int) -> list[Person]:
    """Deterministyczna próbka profili - ten sam wsad przy każdym wywołaniu.

    Determinizm jest tu warunkiem sensu testów: porównujemy wynik tego samego
    wsadu przy dwóch budżetach pracy, więc losowość zamieniłaby asercję
    w rzut monetą.
    """
    levels = [
        ExperienceLevel.BEGINNER,
        ExperienceLevel.INTERMEDIATE,
        ExperienceLevel.ADVANCED,
        None,
    ]
    roles = list(PreferredRole) + [None]
    return [Person(f"P{i}", levels[i % 4], roles[i % 8], ["python"]) for i in range(count)]


async def _delete_by_prefix(prefix: str) -> None:
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE submissions SET team_id=NULL WHERE email LIKE :p"), {"p": f"{prefix}%"}
        )
        await conn.execute(text("DELETE FROM submissions WHERE email LIKE :p"), {"p": f"{prefix}%"})
        await conn.execute(
            text(
                "DELETE FROM teams WHERE id NOT IN (SELECT DISTINCT team_id FROM submissions WHERE team_id IS NOT NULL)"
            )
        )
    await engine.dispose()


@pytest.fixture
def email_prefix() -> str:
    prefix = f"hard-{uuid4().hex[:10]}-"
    yield prefix
    asyncio.run(_delete_by_prefix(prefix))


def test_parallel_matching_is_rejected_with_409() -> None:
    """#56: gdy inny przebieg trzyma zamek, żądanie dostaje natychmiastową
    odmowę zamiast czekać w kolejce i po cichu nadpisać wynik poprzednika.

    Współbieżność symulujemy deterministycznie: osobne połączenie bierze
    advisory lock (transakcyjny, więc trzymany dopóki transakcja żyje)
    i w tym oknie wykonujemy prawdziwy POST przez aplikację.
    """

    async def scenario() -> tuple[int, str]:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                locked = await conn.execute(
                    text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": MATCHING_LOCK_KEY}
                )
                assert locked.scalar_one() is True

                response = await asyncio.to_thread(client.post, "/api/match")
                await conn.rollback()  # zwalnia zamek
                return response.status_code, response.json()["detail"]
        finally:
            await engine.dispose()

    status_code, detail = asyncio.run(scenario())

    assert status_code == 409
    assert "już trwa" in detail


def test_matching_available_again_after_lock_released(email_prefix: str) -> None:
    """Zamek jest transakcyjny - po zakończeniu przebiegu kolejne żądanie
    przechodzi normalnie. Bez tego testu moglibyśmy zablokować się na stałe."""
    for i in range(2):
        created = client.post("/api/submissions", json=_payload(email_prefix, i))
        assert created.status_code == 201

    response = client.post("/api/match?team_size=2")

    assert response.status_code == 201


def test_two_real_parallel_match_requests_one_wins_one_gets_409(
    email_prefix: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uwaga z review #83: pełny cykl weź-policz-zwolnij pod realną nakładką.

    Dwa PRAWDZIWE żądania POST /api/match naraz (httpx.AsyncClient +
    asyncio.gather), nie ręcznie trzymany zamek. Algorytm jest spowolniony
    wrapperem, żeby nakładka była gwarantowana, a nie zależna od timingu.
    Ten test przechodzi tylko dzięki asyncio.to_thread w serwisie: bez niego
    pierwszy przebieg blokowałby event loop, drugi nie ruszyłby przed końcem
    pierwszego i oba skończyłyby z 201.
    """
    for i in range(2):
        assert client.post("/api/submissions", json=_payload(email_prefix, i)).status_code == 201

    from app.enums import MatchingAlgorithm

    real_algorithm = matching_service.ALGORITHMS[MatchingAlgorithm.BALANCED]

    def slow_algorithm(submissions, team_size):
        time.sleep(0.4)
        return real_algorithm(submissions, team_size)

    monkeypatch.setitem(matching_service.ALGORITHMS, MatchingAlgorithm.BALANCED, slow_algorithm)

    async def scenario() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
            return list(
                await asyncio.gather(
                    async_client.post("/api/match?team_size=2"),
                    async_client.post("/api/match?team_size=2"),
                )
            )

    first, second = asyncio.run(scenario())

    codes = sorted([first.status_code, second.status_code])
    assert codes == [201, 409]
    loser = first if first.status_code == 409 else second
    assert "już trwa" in loser.json()["detail"]


def test_submission_limit_returns_409(email_prefix: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """#57 warstwa 1: powyżej limitu POST /api/submissions odmawia po polsku.

    Limit zbijamy do 2, żeby nie wstawiać w CI trzech tysięcy rekordów -
    mechanizm jest identyczny, różni się tylko stała.
    """

    # Limit wzgledem BIEZACEGO stanu bazy: inne testy w tym samym biegu
    # zostawiaja swoje rekordy do czasu wlasnego sprzatania, wiec bezwzgledna
    # "2" bylaby loteria zalezna od kolejnosci testow.
    async def current_count() -> int:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT count(*) FROM submissions"))
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    monkeypatch.setattr(
        submissions_service, "MAX_TOTAL_SUBMISSIONS", asyncio.run(current_count()) + 2
    )

    assert client.post("/api/submissions", json=_payload(email_prefix, 0)).status_code == 201
    assert client.post("/api/submissions", json=_payload(email_prefix, 1)).status_code == 201

    third = client.post("/api/submissions", json=_payload(email_prefix, 2))

    assert third.status_code == 409
    assert "limit zgłoszeń" in third.json()["detail"]


def test_participant_cap_on_matching_returns_409(
    email_prefix: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#57 warstwa 2: niezależna zapadka na wejściu do algorytmu."""
    monkeypatch.setattr(matching_service, "MAX_MATCHED_PARTICIPANTS", 3)

    for i in range(4):
        assert client.post("/api/submissions", json=_payload(email_prefix, i)).status_code == 201

    response = client.post("/api/match?team_size=2")

    assert response.status_code == 409
    assert "Zbyt wiele zgłoszeń" in response.json()["detail"]


def test_tiny_repair_budget_still_yields_valid_teams(monkeypatch: pytest.MonkeyPatch) -> None:
    """#57 warstwa 3: wyczerpany budżet kończy naprawę, ale wynik pozostaje
    poprawnym podziałem - gwarancje pochodzą z faz 1-3, nie z naprawy."""
    monkeypatch.setattr(balanced_module, "_MAX_REPAIR_WORK", 1)

    people = _people(23)

    teams = balanced_module.balanced_teams(people, 4)

    assert sorted(len(t) for t in teams) == sorted(team_sizes(23, 4))
    assigned = [p for team in teams for p in team]
    assert sorted(id(p) for p in assigned) == sorted(id(p) for p in people)

    # Gwarancja nie-beginnera obowiązuje także przy zerowym budżecie naprawy.
    non_beginners = sum(1 for p in people if balanced_module.experience_points(p) >= 2)
    assert non_beginners >= len(teams)
    for team in teams:
        assert any(balanced_module.experience_points(p) >= 2 for p in team)


def test_repair_budget_actually_stops_the_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    """#57 warstwa 3: budżet naprawdę ucina naprawę, a nie tylko istnieje.

    Test powyżej pilnuje, żeby wynik po wyczerpaniu budżetu pozostał poprawny -
    ale przechodzi również wtedy, gdy limitu nie ma w kodzie w ogóle, bo pełna
    naprawa też daje poprawny podział. Bez tej asercji skasowanie warunku
    w `_swap_repair` przeszłoby CI bez ani jednego czerwonego testu, a to
    właśnie ten warunek jest obroną przed DoS z #57.

    Mechanizm sprawdzamy porównaniem: ten sam wsad, dwa budżety. Przy budżecie
    wyczerpanym naprawa kończy się przed czasem, więc wynik musi być ŚCIŚLE
    gorszy (`objective`: niższy = lepszy). Wsad dobrany tak, żeby fazy 1-3
    zostawiały naprawie realny zysk do wzięcia - inaczej oba przebiegi
    dawałyby to samo i test nie mierzyłby niczego.
    """
    monkeypatch.setattr(balanced_module, "_MAX_REPAIR_WORK", 10**12)
    full = balanced_module.objective(balanced_module.balanced_teams(_people(30), 4))

    monkeypatch.setattr(balanced_module, "_MAX_REPAIR_WORK", 1)
    truncated = balanced_module.objective(balanced_module.balanced_teams(_people(30), 4))

    assert truncated > full
