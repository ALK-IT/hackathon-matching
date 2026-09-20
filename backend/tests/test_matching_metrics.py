"""Testy metryki jakości dopasowania i porównania algorytmów (#26)."""

from dataclasses import asdict, dataclass, field, fields

import pytest

from app.enums import ExperienceLevel, PreferredRole
from app.matching.balanced import balanced_teams
from app.matching.baseline import random_teams
from app.matching.compare import LABELS, compare_algorithms, main
from app.matching.metrics import TeamScore, score_teams

ADVANCED = ExperienceLevel.ADVANCED
INTERMEDIATE = ExperienceLevel.INTERMEDIATE
BEGINNER = ExperienceLevel.BEGINNER


@dataclass
class Person:
    """Tyle, ile czyta metryka - bez bazy i bez modelu ORM."""

    experience_level: ExperienceLevel | None
    preferred_role: PreferredRole | None
    skills: list[str] = field(default_factory=list)
    availability: bool = True


def test_every_measure_on_a_hand_computed_split() -> None:
    """Każda miara policzona ręcznie na małym przykładzie - obok rachunek."""
    team_a = [
        Person(ADVANCED, PreferredRole.BACKEND, ["python", "sql"]),
        Person(BEGINNER, PreferredRole.FRONTEND, ["python"], availability=False),
    ]
    team_b = [
        Person(BEGINNER, PreferredRole.DESIGN, ["figma"]),
        Person(None, None, ["figma", "css"], availability=False),
        Person(BEGINNER, PreferredRole.FRONTEND, [], availability=False),
    ]

    score = score_teams([team_a, team_b])

    assert asdict(score) == pytest.approx(
        {
            "experience_spread": 2,  # A: 3+1 = 4, B: 1+0+1 = 2
            "teams_without_backend_pct": 50.0,  # backendowiec tylko w A
            "teams_without_frontend_pct": 0.0,  # frontendowiec w obu
            "role_spread": 2 / 7,  # backend 1-0, design 0-1, pozostałe 5 ról po 0
            "duplicate_skills_per_team": 1.0,  # A: python x2, B: figma x2 -> 2 / 2 zespoły
            "size_spread": 1,  # 2 i 3 osoby
            "teams_without_experienced_pct": 50.0,  # w B sami początkujący i brak poziomu
            "availability_spread": 1,  # niedostępni: A 1, B 2
            "objective": 100_000 * 2 + 1_000 * 2 + 2,  # wagi z balanced.objective
        }
    )


def test_no_teams_give_zeros() -> None:
    """Pusty podział nie ma czego oceniać - zera zamiast wyjątku z max()."""
    assert score_teams([]) == TeamScore(0, 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0, 0)


def test_accepts_real_submission_model() -> None:
    """Produkcyjnie metryka dostanie zgłoszenia z bazy - model musi pasować
    do protokołu. Obiekty budowane w pamięci, bez bazy."""
    from app.models import Submission

    submissions = [
        Submission(
            full_name=f"Osoba {index}",
            email=f"osoba{index}@example.com",
            skills=["python"],
            experience_level=level,
            preferred_role=PreferredRole.BACKEND,
            availability=True,
        )
        for index, level in enumerate([ADVANCED, BEGINNER, INTERMEDIATE, BEGINNER])
    ]

    score = score_teams(balanced_teams(submissions, 2))

    assert score.size_spread == 0
    assert score.teams_without_experienced_pct == 0.0


def test_algorithm_compared_with_itself_ties_everywhere() -> None:
    """Sprawdzian samego porównania: te same dane i to samo ziarno dają ten
    sam podział, więc każda miara musi wyjść remisem - bez tego bilans
    "lepszy / gorszy" mógłby coś przekłamywać."""
    for comparison in compare_algorithms(random_teams, random_teams, datasets=10, seed=1):
        assert (comparison.better, comparison.worse, comparison.ties) == (0, 0, 10)
        assert comparison.candidate_mean == comparison.baseline_mean


def test_balanced_beats_random_on_the_same_data() -> None:
    """Kryterium akceptacji z #26: na tych samych danych balanced wypada lepiej.

    40 zestawów zamiast jednego - pojedynczy zestaw losowanie czasem trafi
    dobrze samo z siebie.
    """
    results = {
        comparison.measure: comparison
        for comparison in compare_algorithms(balanced_teams, random_teams, datasets=40, seed=2026)
    }

    # Średnio lepiej we wszystkim, co balanced poprawia: w składnikach
    # `objective` (doświadczenie, role, umiejętności) i w miarach, których
    # `objective` nie liczy (pokrycie ról, zespoły bez doświadczonej osoby).
    for measure in (
        "experience_spread",
        "role_spread",
        "duplicate_skills_per_team",
        "objective",
        "teams_without_backend_pct",
        "teams_without_frontend_pct",
        "teams_without_experienced_pct",
    ):
        assert results[measure].candidate_mean < results[measure].baseline_mean, measure

    # Główne kryterium: praktycznie nigdy gorzej zestaw po zestawie. To
    # obserwacja, nie gwarancja - naprawa wymianami potrafi utknąć (przy 3000
    # zestawach zdarza się jedna przegrana), stąd margines zamiast `worse == 0`.
    # Warunek wymusza też prawdziwe zwycięstwa: bilans z samych remisów nie przejdzie.
    spread = results["experience_spread"]
    assert spread.better > 10 * spread.worse

    # Miara kontrolna: oba algorytmy dzielą według team_sizes.
    assert results["size_spread"].ties == 40

    # `availability_spread` celowo bez asercji: algorytm nie bierze dziś
    # dostępności pod uwagę (#58), a test nie może się wywrócić, kiedy #58
    # to naprawi.


def test_tally_and_means_on_known_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bilans i średnie na podstawionych wynikach, bez losowania.

    Porównanie woła `score_teams` na przemian: kandydat, potem odniesienie,
    zestaw po zestawie. Kandydat dostaje rozrzuty 1, 2, 3, odniesienie 2, 2, 1,
    więc bilans musi wyjść dokładnie 1 lepszy / 1 remis / 1 gorszy.
    """
    spreads = iter([1, 2, 2, 2, 3, 1])

    def fake_score(_teams: object) -> TeamScore:
        return TeamScore(next(spreads), 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0, 0)

    monkeypatch.setattr("app.matching.compare.score_teams", fake_score)

    results = {
        comparison.measure: comparison
        for comparison in compare_algorithms(random_teams, random_teams, datasets=3, seed=1)
    }

    spread = results["experience_spread"]
    assert (spread.better, spread.ties, spread.worse) == (1, 1, 1)
    assert spread.candidate_mean == pytest.approx(2.0)
    assert spread.baseline_mean == pytest.approx(5 / 3)


def test_comparison_needs_at_least_one_dataset() -> None:
    with pytest.raises(ValueError):
        compare_algorithms(balanced_teams, random_teams, datasets=0, seed=1)


@pytest.mark.parametrize("value", ["0", "-3", "abc"])
def test_script_rejects_invalid_dataset_count(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Zła liczba zestawów kończy się czytelnym błędem argparse, a nie
    tracebackiem z głębi porównania."""
    with pytest.raises(SystemExit):
        main(["--datasets", value])

    assert "musi byc liczba dodatnia" in capsys.readouterr().err


def test_script_prints_a_row_for_every_measure(capsys: pytest.CaptureFixture[str]) -> None:
    """Każde pole `TeamScore` ma etykietę i wiersz w tabeli skryptu - nowa miara
    bez etykiety wywróciłaby się tu, a nie dopiero przy prezentacji."""
    main(["--datasets", "3", "--seed", "1"])

    output = capsys.readouterr().out
    for measure in fields(TeamScore):
        assert LABELS[measure.name] in output
