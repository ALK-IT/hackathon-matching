import random
import statistics
from dataclasses import dataclass, field

import pytest

from app.enums import ExperienceLevel, PreferredRole
from app.matching.balanced import balanced_teams, team_experience_points
from app.matching.baseline import random_teams, team_sizes

BEGINNER = ExperienceLevel.BEGINNER
INTERMEDIATE = ExperienceLevel.INTERMEDIATE
ADVANCED = ExperienceLevel.ADVANCED


@dataclass
class Person:
    """Uczestnik na potrzeby testów - tyle, ile wymaga protokół `Participant`.

    Zwykła dataclass zamiast modelu `Submission`: algorytm czyta trzy pola
    i nie dotyka bazy, więc stawianie Postgresa nic by tu nie sprawdziło,
    a test byłby wolny i zależny od migracji.
    """

    name: str
    experience_level: ExperienceLevel | None = None
    preferred_role: PreferredRole | None = None
    skills: list[str] = field(default_factory=list)


def _people(
    level: ExperienceLevel | None,
    count: int,
    *,
    role: PreferredRole | None = None,
    prefix: str = "",
) -> list[Person]:
    """`count` osób o tym samym poziomie - do budowania czytelnych zestawów."""
    label = prefix or (level.value if level else "brak")
    return [Person(f"{label}-{index}", level, role) for index in range(count)]


def _levels(teams: list[list[Person]]) -> list[list[ExperienceLevel | None]]:
    return [[member.experience_level for member in team] for team in teams]


def _points(teams: list[list[Person]]) -> list[int]:
    return [team_experience_points(team) for team in teams]


def _random_people(rng: random.Random, count: int) -> list[Person]:
    levels = [None, BEGINNER, INTERMEDIATE, ADVANCED]
    roles = list(PreferredRole)
    return [
        Person(f"osoba-{index}", rng.choice(levels), rng.choice(roles)) for index in range(count)
    ]


# --- krok 1: podział na zespoły taki sam jak w baseline ---


def test_team_sizes_match_baseline_split() -> None:
    """Krok 1 to ten sam podział co w baseline - limit jest maksimum, nie celem."""
    teams = balanced_teams(_people(INTERMEDIATE, 9), 4)

    assert [len(team) for team in teams] == [3, 3, 3]


def test_no_submissions_give_no_teams() -> None:
    assert balanced_teams([], 4) == []


def test_fewer_submissions_than_team_size_give_single_team() -> None:
    teams = balanced_teams(_people(BEGINNER, 2), 4)

    assert len(teams) == 1
    assert len(teams[0]) == 2


def test_invalid_team_size_is_rejected() -> None:
    """Bezsensowny parametr ma dać jasny błąd, a nie pustą listę (SECURITY.md)."""
    with pytest.raises(ValueError):
        balanced_teams(_people(BEGINNER, 5), 0)


@pytest.mark.parametrize("team_size", [2, 3, 4, 5])
@pytest.mark.parametrize("participant_count", range(1, 30))
def test_everyone_lands_in_exactly_one_team(participant_count: int, team_size: int) -> None:
    """Podstawowa gwarancja: nikt nie ginie i nikt się nie dubluje."""
    people = _random_people(random.Random(participant_count), participant_count)

    teams = balanced_teams(people, team_size)

    assigned = [member.name for team in teams for member in team]
    assert sorted(assigned) == sorted(person.name for person in people)
    assert [len(team) for team in teams] == team_sizes(participant_count, team_size)


def test_input_list_is_not_modified() -> None:
    """Funkcja jest czysta - także wtedy, gdy dostaje własny generator."""
    people = _people(ADVANCED, 6)
    original = list(people)

    balanced_teams(people, 3, rng=random.Random(11))

    assert people == original


# --- krok 2: wyrównanie sum punktów za doświadczenie ---


def test_example_from_issue_gives_almost_equal_points() -> None:
    """Przykład z zadania: 3 zaawansowanych, 4 średnich, 2 początkujących.

    9 osób przy limicie 4 to trzy zespoły po 3. Punktów jest 3*3 + 4*2 + 2*1 = 19,
    czyli idealny podział (19/3) jest niemożliwy - najlepsze, co się da, to 7/6/6.
    """
    people = _people(ADVANCED, 3) + _people(INTERMEDIATE, 4) + _people(BEGINNER, 2)

    teams = balanced_teams(people, 4)

    assert sorted(_points(teams)) == [6, 6, 7]


def test_strongest_people_are_spread_across_teams() -> None:
    """Zaawansowani nie mogą wylądować w jednym zespole."""
    people = _people(ADVANCED, 3) + _people(BEGINNER, 6)

    teams = balanced_teams(people, 3)

    assert all(ADVANCED in levels for levels in _levels(teams))


def test_no_team_is_only_beginners() -> None:
    """Kryterium akceptacji z issue: zespół samych początkujących nie ma prawa powstać.

    Osób o wyższym poziomie jest tu tyle samo, ile zespołów - czyli dokładnie
    tyle, ile trzeba, żeby każdy zespół dostał jedną. Ten przypadek jest
    najciaśniejszy: przy jednym błędzie w rozstawianiu któryś zespół zostaje
    z samymi początkującymi.
    """
    people = _people(ADVANCED, 2) + _people(INTERMEDIATE, 2) + _people(BEGINNER, 8)

    teams = balanced_teams(people, 3)

    assert len(teams) == 4
    for levels in _levels(teams):
        assert set(levels) != {BEGINNER}


@pytest.mark.parametrize("team_size", [2, 3, 4, 5])
@pytest.mark.parametrize("seed", range(15))
def test_point_spread_stays_small(seed: int, team_size: int) -> None:
    """Rozrzut sum punktów nie przekracza wagi jednej osoby (maksymalnie 3).

    To realna gwarancja tej heurystyki: skoro zawsze dokładamy do najuboższego
    zespołu, żaden nie może odstać od reszty bardziej niż o pojedynczy wkład.
    """
    people = _random_people(random.Random(seed), 20)

    points = _points(balanced_teams(people, team_size))

    assert max(points) - min(points) <= 3


def test_missing_experience_level_does_not_crash() -> None:
    """Zgłoszenia sprzed rozszerzenia modelu mają `None` - liczą się jako 0 punktów."""
    people = _people(None, 4) + _people(ADVANCED, 2)

    teams = balanced_teams(people, 3)

    assert sorted(_points(teams)) == [3, 3]


def test_balanced_teams_beat_random_teams_on_point_spread() -> None:
    """Test porównawczy z issue: to ma być mierzalnie lepsze niż losowanie.

    Miarą jest odchylenie standardowe sum punktów w zespołach (im niżej, tym
    równiej). Sprawdzamy je na 50 losowych zestawach zgłoszeń - pojedynczy
    przypadek nic by nie znaczył, bo losowanie czasem trafi dobrze samo z siebie.
    """
    balanced_spread: list[float] = []
    random_spread: list[float] = []

    for seed in range(50):
        rng = random.Random(seed)
        people = _random_people(rng, 24)

        balanced_spread.append(statistics.pstdev(_points(balanced_teams(people, 4))))
        random_spread.append(statistics.pstdev(_points(random_teams(people, 4, rng=rng))))

    assert statistics.mean(balanced_spread) < statistics.mean(random_spread)
    # Nie tylko "średnio lepiej": w żadnym pojedynczym zestawie losowanie
    # nie może wypaść równiej niż algorytm, który akurat to wyrównuje.
    assert all(
        wyrownany <= losowy
        for wyrownany, losowy in zip(balanced_spread, random_spread, strict=True)
    )


# --- krok 3: dobór konkretnych osób pod role i umiejętności ---


def test_roles_are_spread_within_the_same_level() -> None:
    """Przykład z zadania: przy równym poziomie decyduje brakująca rola.

    Czterech średniozaawansowanych - dwóch z frontendu, dwóch z backendu.
    Zespoły są dwuosobowe, więc jedyny sensowny wynik to front + backend
    w każdym z nich.
    """
    people = [
        Person("fe-1", INTERMEDIATE, PreferredRole.FRONTEND),
        Person("fe-2", INTERMEDIATE, PreferredRole.FRONTEND),
        Person("be-1", INTERMEDIATE, PreferredRole.BACKEND),
        Person("be-2", INTERMEDIATE, PreferredRole.BACKEND),
    ]

    teams = balanced_teams(people, 2)

    for team in teams:
        assert {member.preferred_role for member in team} == {
            PreferredRole.FRONTEND,
            PreferredRole.BACKEND,
        }


def test_role_diversity_wins_over_input_order() -> None:
    """Kolejność zgłoszeń nie może wygrać z uzupełnieniem składu.

    Wszyscy są zaawansowani, więc krok 2 nie ma tu nic do powiedzenia - liczy
    się wyłącznie to, że pierwszy zespół dostał już frontendowca, a w kolejce
    stoi drugi frontendowiec i backendowiec.
    """
    people = [
        Person("fe-1", ADVANCED, PreferredRole.FRONTEND),
        Person("fe-2", ADVANCED, PreferredRole.FRONTEND),
        Person("be-1", ADVANCED, PreferredRole.BACKEND),
        Person("be-2", ADVANCED, PreferredRole.BACKEND),
    ]

    teams = balanced_teams(people, 2)

    assert [member.name for member in teams[0]] == ["fe-1", "be-1"]
    assert [member.name for member in teams[1]] == ["fe-2", "be-2"]


def test_skills_break_ties_between_equal_roles() -> None:
    """Gdy role są takie same, wygrywa osoba wnosząca nowe umiejętności.

    Wszyscy są backendowcami na tym samym poziomie - jedyne, co ich różni, to
    umiejętności. Do zespołu z "python" ma trafić osoba od "go", a nie druga
    znająca dokładnie to samo.
    """
    people = [
        Person("python-1", INTERMEDIATE, PreferredRole.BACKEND, ["python"]),
        Person("python-2", INTERMEDIATE, PreferredRole.BACKEND, ["python"]),
        Person("go-1", INTERMEDIATE, PreferredRole.BACKEND, ["go"]),
        Person("go-2", INTERMEDIATE, PreferredRole.BACKEND, ["go"]),
    ]

    teams = balanced_teams(people, 2)

    for team in teams:
        assert {skill for member in team for skill in member.skills} == {"python", "go"}


# --- powtarzalność ---


def test_result_is_deterministic_without_rng() -> None:
    """Bez `rng` ten sam input daje ten sam podział - inaczej nie da się
    porównywać algorytmów ani odtworzyć raz pokazanego rozstawienia."""
    people = _random_people(random.Random(99), 15)

    assert balanced_teams(people, 4) == balanced_teams(people, 4)


def test_same_seed_gives_same_teams() -> None:
    """`rng` przestawia tylko kolejność wejścia, więc też musi być powtarzalny."""
    people = _random_people(random.Random(5), 15)

    first = balanced_teams(people, 4, rng=random.Random(7))
    second = balanced_teams(people, 4, rng=random.Random(7))

    assert first == second


def test_rng_keeps_the_balance_guarantees() -> None:
    """Losowa kolejność wejścia nie może zepsuć wyrównania - zmienia tylko remisy."""
    people = _people(ADVANCED, 3) + _people(INTERMEDIATE, 4) + _people(BEGINNER, 2)

    for seed in range(10):
        teams = balanced_teams(people, 4, rng=random.Random(seed))

        assert sorted(_points(teams)) == [6, 6, 7]
