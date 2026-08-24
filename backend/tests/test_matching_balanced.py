import random
from dataclasses import dataclass, field
from statistics import pstdev

import pytest

from app.enums import ExperienceLevel, PreferredRole
from app.matching.balanced import _RANKS, balanced_teams, objective
from app.matching.baseline import random_teams, team_sizes


@dataclass
class Person:
    """Lekki profil zamiast modelu SQLAlchemy - algorytm czyta tylko te pola."""

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


def rank_sum(team: list[Person]) -> int:
    return sum(_RANKS[p.experience_level] for p in team)


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
def test_split_keeps_baseline_invariants(count: int, team_size: int) -> None:
    """Te same gwarancje co random_teams: nikt nie ginie, nikt się nie dubluje,
    rozmiary dokładnie jak z team_sizes."""
    people = make_people(count)

    teams = balanced_teams(people, team_size, rng=random.Random(count))

    assert sorted(len(t) for t in teams) == sorted(team_sizes(count, team_size))
    assigned = [p for team in teams for p in team]
    assert sorted(id(p) for p in assigned) == sorted(id(p) for p in people)


@pytest.mark.parametrize("team_size", [2, 3, 4, 5])
@pytest.mark.parametrize("count", range(2, 40))
def test_every_team_gets_a_non_beginner_when_supply_allows(count: int, team_size: int) -> None:
    """Twarde kryterium z #24, w wersji z warunkiem wstępnym: gwarancja
    obowiązuje, gdy nie-beginnerów starcza dla wszystkich zespołów."""
    people = make_people(count)
    teams = balanced_teams(people, team_size, rng=random.Random(count))

    non_beginners = sum(1 for p in people if _RANKS[p.experience_level] >= 2)
    if non_beginners < len(teams):
        pytest.skip("za mało nie-beginnerów, gwarancja nie obowiązuje")

    for team in teams:
        assert any(_RANKS[p.experience_level] >= 2 for p in team)


@pytest.mark.parametrize("team_size", [2, 3, 4, 5])
@pytest.mark.parametrize("count", range(2, 40))
def test_roles_spread_evenly(count: int, team_size: int) -> None:
    """Uwzględnienie ról przy doświadczeniu jako kryterium nadrzędnym.

    Decyzja zespołu: najpierw wyrównujemy doświadczenie, rola jest niżej.
    Przy tej hierarchii idealny rozrzut (różnica 1) nie jest gwarantowany -
    test pilnuje zmierzonej granicy 2 jako regresji; naprawa wymianami
    sprowadza zdecydowaną większość przypadków do 1.

    Dotyczy ZADEKLAROWANYCH ról. None ("nie podano") to brak danych, nie
    rola - dwie takie osoby w jednym zespole nie tworzą monokultury.
    """
    people = make_people(count)
    teams = balanced_teams(people, team_size, rng=random.Random(count))

    for role in PreferredRole:
        counts = [sum(1 for p in team if p.preferred_role == role) for team in teams]
        assert max(counts) - min(counts) <= 2, f"rola {role}: {counts}"


def test_roles_spread_better_than_random_in_aggregate() -> None:
    """Rola jest kryterium drugorzędnym, więc pojedynczy przypadek bywa gorszy
    od losowego - ale w agregacie po siatce balanced ma rozkładać role
    wyraźnie lepiej niż random_teams. Ziarna stałe, wynik deterministyczny."""
    total_balanced = 0
    total_random = 0
    # Siatka próbkowana co 3 - agregat pozostaje rozstrzygający, a czas maleje.
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


def test_skills_diversified_within_teams() -> None:
    """Balans umiejętności: osoby o tym samym skillu rozchodzą się po
    zespołach. Konstrukcja wymusza jednoznaczny optymalny układ: dwa zespoły
    po jednym pythonowcu i jednym reactowcu, zero powtórzeń."""
    people = [
        Person("A", ExperienceLevel.INTERMEDIATE, None, skills=["python"]),
        Person("B", ExperienceLevel.INTERMEDIATE, None, skills=["python"]),
        Person("C", ExperienceLevel.INTERMEDIATE, None, skills=["react"]),
        Person("D", ExperienceLevel.INTERMEDIATE, None, skills=["react"]),
    ]

    teams = balanced_teams(people, 2, rng=random.Random(0))

    assert skill_duplicates(teams) == 0
    for team in teams:
        assert {s for p in team for s in p.skills} == {"python", "react"}


def test_skill_duplicates_lower_than_random_in_aggregate() -> None:
    """Trzecie kryterium hierarchii: w agregacie po siatce zespoły mają
    mniej powtórzonych umiejętności niż przy podziale losowym."""
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


def test_objective_not_worse_than_random_in_aggregate() -> None:
    """Naprawa optymalizuje objective, więc wynik balanced ma być w agregacie
    lepszy (niższy) niż układ losowy - to domyka spójność algorytm-metryka."""
    total_balanced = 0
    total_random = 0
    for team_size in (3, 4):
        for count in range(4, 40, 3):
            people = make_people(count)
            total_balanced += objective(balanced_teams(people, team_size, rng=random.Random(count)))
            total_random += objective(random_teams(people, team_size, rng=random.Random(count)))

    assert total_balanced < total_random


def test_mixed_levels_never_give_all_beginner_team() -> None:
    """Literalne kryterium akceptacji: mieszane poziomy -> żaden zespół
    nie składa się z samych beginnerów."""
    people = make_people(12)  # cykl daje 3 beginnerów, 3 intermediate, 3 advanced, 3 None

    teams = balanced_teams(people, 3, rng=random.Random(0))

    for team in teams:
        assert not all(p.experience_level in (ExperienceLevel.BEGINNER, None) for p in team), [
            p.name for p in team
        ]


def test_more_even_experience_than_random_baseline() -> None:
    """Opcjonalne kryterium z #24: rozkład doświadczenia bardziej wyrównany
    niż u random_teams - mierzone odchyleniem sum rang (pełna metryka: #26)."""
    people = make_people(24)

    balanced = balanced_teams(people, 4, rng=random.Random(5))
    baseline = random_teams(people, 4, rng=random.Random(5))

    spread_balanced = pstdev(rank_sum(t) for t in balanced)
    spread_baseline = pstdev(rank_sum(t) for t in baseline)
    assert spread_balanced <= spread_baseline


def test_same_rng_gives_same_teams() -> None:
    people = make_people(17)
    first = balanced_teams(people, 4, rng=random.Random(9))
    second = balanced_teams(people, 4, rng=random.Random(9))
    assert first == second


def test_input_list_is_not_modified() -> None:
    people = make_people(11)
    original = list(people)
    balanced_teams(people, 3, rng=random.Random(1))
    assert people == original


@pytest.mark.parametrize("team_size", [0, -2])
def test_invalid_team_size_raises(team_size: int) -> None:
    with pytest.raises(ValueError):
        balanced_teams(make_people(4), team_size)


def test_all_none_profiles_still_split_correctly() -> None:
    """Zgłoszenia sprzed #43 (brak poziomu, roli i umiejętności) nie
    wywracają algorytmu."""
    people = [Person(f"P{i}", None, None, skills=[]) for i in range(7)]

    teams = balanced_teams(people, 3, rng=random.Random(2))

    assert sorted(len(t) for t in teams) == sorted(team_sizes(7, 3))


def test_accepts_real_submission_model() -> None:
    """Submission spełnia protokół - tak wywoła to #25. Bez bazy: obiekty
    tworzone w pamięci."""
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
