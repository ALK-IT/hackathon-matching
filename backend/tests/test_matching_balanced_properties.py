"""Testy własnościowe balanced_teams - siatki i agregaty.

Uzupełnienie testów zachowań z test_matching_balanced.py: zamiast pojedynczych
scenariuszy sprawdzają niezmienniki na siatce kombinacji liczebności i limitów
oraz przewagę nad random_teams w agregacie. Deterministyczne (stałe ziarna).
"""

import random
from dataclasses import dataclass, field

import pytest

from app.enums import ExperienceLevel, PreferredRole
from app.matching.balanced import balanced_teams, experience_points, objective
from app.matching.baseline import random_teams, team_sizes


@dataclass
class Person:
    """Tyle, ile wymaga protokół Participant - bez bazy i bez modelu ORM."""

    name: str
    experience_level: ExperienceLevel | None
    preferred_role: PreferredRole | None
    skills: list[str] = field(default_factory=list)


_LEVELS = [ExperienceLevel.BEGINNER, ExperienceLevel.INTERMEDIATE, ExperienceLevel.ADVANCED, None]
_ROLES = list(PreferredRole) + [None]
_SKILLS = ["python", "react", "sql", "docker", "figma"]


def make_people(count: int) -> list[Person]:
    """Deterministyczny mix poziomów, ról i umiejętności - cykle o różnych
    długościach sprawiają, że kombinacje się przeplatają."""
    return [
        Person(
            f"P{i}",
            _LEVELS[i % len(_LEVELS)],
            _ROLES[i % len(_ROLES)],
            skills=[_SKILLS[i % len(_SKILLS)], _SKILLS[(i + 2) % len(_SKILLS)]],
        )
        for i in range(count)
    ]


def skill_duplicates(teams: list[list[Person]]) -> int:
    """Kara za powtórzenia: wystąpienia minus różne, sumowane po zespołach."""
    total = 0
    for team in teams:
        mentions = sum(len(p.skills) for p in team)
        distinct = len({s for p in team for s in p.skills})
        total += mentions - distinct
    return total


@pytest.mark.parametrize("team_size", [2, 3, 4, 5])
@pytest.mark.parametrize("count", range(40))
def test_partition_and_sizes_on_grid(count: int, team_size: int) -> None:
    """Nikt nie ginie, nikt się nie dubluje, rozmiary dokładnie z team_sizes."""
    people = make_people(count)

    teams = balanced_teams(people, team_size, rng=random.Random(count))

    assert sorted(len(t) for t in teams) == sorted(team_sizes(count, team_size))
    assigned = [p for team in teams for p in team]
    assert sorted(id(p) for p in assigned) == sorted(id(p) for p in people)


@pytest.mark.parametrize("team_size", [2, 3, 4, 5])
@pytest.mark.parametrize("count", range(2, 40))
def test_non_beginner_guarantee_on_grid(count: int, team_size: int) -> None:
    """Gwarancja z #24 pod warunkiem wstępnym: gdy osób o poziomie wyższym niż
    początkujący starcza dla wszystkich zespołów, każdy zespół ma taką osobę.
    Sprawdzana również PO kroku naprawy - strażnik nie może jej wypuścić."""
    people = make_people(count)
    teams = balanced_teams(people, team_size, rng=random.Random(count))

    non_beginners = sum(1 for p in people if experience_points(p) >= 2)
    if non_beginners < len(teams):
        pytest.skip("za mało nie-beginnerów, gwarancja nie obowiązuje")

    for team in teams:
        assert any(experience_points(p) >= 2 for p in team)


@pytest.mark.parametrize("team_size", [2, 3, 4, 5])
@pytest.mark.parametrize("count", range(2, 40))
def test_declared_role_spread_bound_on_grid(count: int, team_size: int) -> None:
    """Rozrzut każdej zadeklarowanej roli między zespołami najwyżej 2.

    Rola jest kryterium podrzędnym wobec doświadczenia, więc idealna różnica 1
    nie jest gwarantowana; zmierzona granica po naprawie wymianami to 2
    (na tej siatce niemal zawsze 1) - test pilnuje jej jako regresji.
    None to brak danych, nie rola - bez gwarancji rozrzutu.
    """
    people = make_people(count)
    teams = balanced_teams(people, team_size, rng=random.Random(count))

    for role in PreferredRole:
        counts = [sum(1 for p in team if p.preferred_role == role) for team in teams]
        assert max(counts) - min(counts) <= 2, f"rola {role}: {counts}"


def test_roles_spread_better_than_random_in_aggregate() -> None:
    """W agregacie po próbkowanej siatce role rozłożone lepiej niż losowo."""
    total_balanced = 0
    total_random = 0
    for team_size in (2, 3, 4, 5):
        for count in range(2, 40, 3):
            people = make_people(count)
            bal = balanced_teams(people, team_size, rng=random.Random(count))
            rnd = random_teams(people, team_size, rng=random.Random(count))
            for role in PreferredRole:
                bal_counts = [sum(1 for p in t if p.preferred_role == role) for t in bal]
                rnd_counts = [sum(1 for p in t if p.preferred_role == role) for t in rnd]
                total_balanced += max(bal_counts) - min(bal_counts)
                total_random += max(rnd_counts) - min(rnd_counts)

    assert total_balanced < total_random


def test_skill_duplicates_lower_than_random_in_aggregate() -> None:
    """Zespoły mają w agregacie mniej powtórzonych umiejętności niż losowe."""
    total_balanced = 0
    total_random = 0
    for team_size in (2, 3, 4, 5):
        for count in range(2, 40, 3):
            people = make_people(count)
            total_balanced += skill_duplicates(
                balanced_teams(people, team_size, rng=random.Random(count))
            )
            total_random += skill_duplicates(
                random_teams(people, team_size, rng=random.Random(count))
            )

    assert total_balanced < total_random


def test_objective_beats_random_in_aggregate() -> None:
    """Krok 4 optymalizuje objective, więc wynik ma być w agregacie lepszy
    (niższy) niż układ losowy - domyka spójność algorytm-metryka."""
    total_balanced = 0
    total_random = 0
    for team_size in (3, 4):
        for count in range(4, 40, 3):
            people = make_people(count)
            total_balanced += objective(balanced_teams(people, team_size, rng=random.Random(count)))
            total_random += objective(random_teams(people, team_size, rng=random.Random(count)))

    assert total_balanced < total_random


def test_accepts_real_submission_model() -> None:
    """Submission spełnia protokół Participant - tak wywoła to #25.
    Obiekty budowane w pamięci, bez bazy."""
    from app.models import Submission

    subs = [
        Submission(
            full_name=f"U{i}",
            email=f"u{i}@x.pl",
            skills=[_SKILLS[i % len(_SKILLS)]],
            experience_level=_LEVELS[i % 3],
            preferred_role=_ROLES[i % 3],
        )
        for i in range(9)
    ]

    teams = balanced_teams(subs, 3, rng=random.Random(3))

    assert [len(t) for t in teams] == [3, 3, 3]
