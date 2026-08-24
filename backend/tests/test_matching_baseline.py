import random

import pytest

from app.matching.baseline import random_teams, team_sizes


def _participants(count: int) -> list[str]:
    """Uczestnicy jako zwykłe stringi - algorytm nie zagląda do środka.

    Testowanie na modelu `Submission` wymagałoby bazy i niczego by nie
    sprawdziło ponad to: `random_teams` tasuje i tnie listę, nie czyta pól.
    """
    return [f"uczestnik-{index}" for index in range(count)]


# --- sam podział, bez losowości: wynik w pełni przewidywalny ---


def test_nine_participants_with_limit_four_give_three_equal_teams() -> None:
    """Przypadek z opisu zadania: limit to maksimum, nie cel.

    Naiwne cięcie po `team_size` dałoby 4+4+1, czyli zespół jednoosobowy obok
    dwóch pełnych. Ten sam komplet ludzi mieści się w trzech zespołach po 3 -
    i tak ma działać ta funkcja.
    """
    assert team_sizes(9, 4) == [3, 3, 3]


def test_ten_participants_with_limit_three_are_split_evenly() -> None:
    """Kryterium akceptacji z issue: 10 osób, limit 3 -> 4 zespoły."""
    assert team_sizes(10, 3) == [3, 3, 2, 2]


def test_fewer_participants_than_limit_give_single_team() -> None:
    assert team_sizes(2, 4) == [2]


def test_no_participants_give_no_teams() -> None:
    assert team_sizes(0, 4) == []


def test_team_sizes_reject_invalid_team_size() -> None:
    with pytest.raises(ValueError):
        team_sizes(10, 0)


@pytest.mark.parametrize("team_size", [1, 2, 3, 4, 5, 7])
@pytest.mark.parametrize("participant_count", range(40))
def test_split_always_holds_its_guarantees(participant_count: int, team_size: int) -> None:
    """Trzy własności, na których opiera się cały moduł - dla setek kombinacji.

    Pojedyncze przykłady wyżej są czytelne, ale łatwo trafić akurat te, które
    działają. Tu sprawdzamy: nikt nie ginie, nikt nie przekracza limitu
    i żaden zespół nie jest pusty.
    """
    sizes = team_sizes(participant_count, team_size)

    assert sum(sizes) == participant_count
    assert all(size <= team_size for size in sizes)
    assert all(size >= 1 for size in sizes)


@pytest.mark.parametrize("team_size", [2, 3, 4, 5])
@pytest.mark.parametrize("participant_count", range(1, 40))
def test_teams_differ_by_at_most_one_person(participant_count: int, team_size: int) -> None:
    """ "Najbardziej zrównoważony" znaczy: różnica najwyżej jednej osoby."""
    sizes = team_sizes(participant_count, team_size)

    assert max(sizes) - min(sizes) <= 1


# --- pełna funkcja: podział plus losowa kolejność uczestników ---


def test_ten_submissions_with_limit_three_give_four_teams() -> None:
    """Kryterium akceptacji: każdy uczestnik w dokładnie jednym zespole."""
    submissions = _participants(10)

    teams = random_teams(submissions, 3, rng=random.Random(42))

    assert [len(team) for team in teams] == [3, 3, 2, 2]
    assigned = [participant for team in teams for participant in team]
    assert sorted(assigned) == sorted(submissions)


def test_nine_submissions_with_limit_four_give_three_teams_of_three() -> None:
    teams = random_teams(_participants(9), 4, rng=random.Random(1))

    assert [len(team) for team in teams] == [3, 3, 3]


def test_fewer_submissions_than_team_size_do_not_crash() -> None:
    """Przypadek brzegowy z issue: 2 osoby przy limicie 4 to jeden zespół."""
    teams = random_teams(_participants(2), 4, rng=random.Random(0))

    assert len(teams) == 1
    assert len(teams[0]) == 2


def test_no_submissions_give_empty_list() -> None:
    """Przypadek brzegowy z issue: brak zgłoszeń to pusty wynik, nie wyjątek."""
    assert random_teams([], 4) == []


def test_same_seed_gives_same_teams() -> None:
    """Powtarzalność: to samo ziarno musi dać ten sam podział.

    Bez tego nie da się odtworzyć raz wygenerowanego rozstawienia ani porównać
    baseline'u z kolejnymi algorytmami na tych samych danych.
    """
    submissions = _participants(12)

    first = random_teams(submissions, 4, rng=random.Random(7))
    second = random_teams(submissions, 4, rng=random.Random(7))

    assert first == second


def test_order_is_actually_shuffled() -> None:
    """Losowość ma realnie mieszać, a nie tylko deklarować, że miesza.

    Gdyby ktoś usunął `shuffle`, wszystkie testy wyżej dalej by przeszły -
    rozmiary zespołów by się zgadzały. Ten test tego pilnuje.
    """
    submissions = _participants(20)

    teams = random_teams(submissions, 4, rng=random.Random(3))
    assigned = [participant for team in teams for participant in team]

    assert assigned != submissions


def test_input_list_is_not_modified() -> None:
    """Funkcja jest czysta: nie przestawia listy, którą dostała."""
    submissions = _participants(10)
    original = list(submissions)

    random_teams(submissions, 3, rng=random.Random(5))

    assert submissions == original


def test_random_teams_reject_invalid_team_size() -> None:
    with pytest.raises(ValueError):
        random_teams(_participants(5), 0)
