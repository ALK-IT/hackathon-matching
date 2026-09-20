"""Porównanie algorytmów dopasowania na wielu zestawach danych (#26).

Uruchomienie z katalogu backend/:

    python -m app.matching.compare                  # 300 zestawów, ziarno 2026
    python -m app.matching.compare --datasets 50 --seed 7

Oba algorytmy dostają każdy zestaw w identycznej postaci (te same osoby, ten
sam limit, to samo ziarno), a wynik to średnia każdej miary z `TeamScore` plus
bilans "lepszy / remis / gorszy" liczony zestaw po zestawie. Jeden zestaw nic
by nie znaczył: losowanie czasem trafi dobrze samo z siebie.

Dane są syntetyczne (patrz `synthetic_submissions`), więc liczby opisują
algorytmy, a nie konkretny hackaton.
"""

import argparse
import random
from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Protocol

from app.enums import ExperienceLevel, PreferredRole
from app.matching.balanced import balanced_teams
from app.matching.baseline import random_teams
from app.matching.metrics import TeamScore, score_teams

SKILL_POOL = ("python", "react", "sql", "docker", "figma", "java", "css", "ml", "go", "aws")

# Etykiety bez polskich znaków: skrypt pisze do konsoli, a konsola Windows
# (cp1250) zamienia je na krzaczki.
LABELS: dict[str, str] = {
    "experience_spread": "a) rozrzut doswiadczenia (pkt)",
    "teams_without_backend_pct": "b1) % zespolow bez backendowca",
    "teams_without_frontend_pct": "b2) % zespolow bez frontendowca",
    "role_spread": "b3) rozrzut rol (srednio na role)",
    "duplicate_skills_per_team": "c) powtorzone umiejetnosci / zespol",
    "size_spread": "d) rozrzut wielkosci (kontrolna)",
    "teams_without_experienced_pct": "e) % zespolow bez doswiadczonego",
    # Kierunek tej miary czeka na decyzję w #58 - patrz TeamScore.
    "availability_spread": "f) rozrzut niepelnej dostepnosci (#58)",
    "objective": "objective (wlasny cel algorytmu)",
}


@dataclass
class SyntheticSubmission:
    """Wygenerowane zgłoszenie - dokładnie tyle pól, ile czytają algorytm i metryka."""

    experience_level: ExperienceLevel | None
    preferred_role: PreferredRole | None
    skills: list[str]
    availability: bool


class Algorithm(Protocol):
    """Algorytm w sensie tego porównania: zgłoszenia + limit + generator -> zespoły."""

    def __call__(
        self,
        submissions: list[SyntheticSubmission],
        team_size: int,
        *,
        rng: random.Random | None = None,
    ) -> list[list[SyntheticSubmission]]: ...


@dataclass(frozen=True)
class MeasureComparison:
    """Jedna miara w porównaniu: średnie obu algorytmów i bilans zestawów."""

    measure: str
    candidate_mean: float
    baseline_mean: float
    # Zestawy, w których kandydat wypadł lepiej (niżej), tak samo i gorzej.
    better: int
    ties: int
    worse: int


def synthetic_submissions(rng: random.Random, count: int) -> list[SyntheticSubmission]:
    """Losuje `count` zgłoszeń o prostym, jawnym rozkładzie.

    Poziom i rola równomiernie ze wszystkich wartości, 1-3 umiejętności z puli
    dziesięciu, 80% osób dostępnych przez cały hackaton. Założenia wpływają na
    wartości bezwzględne (np. ile zespołów w ogóle może mieć backendowca), ale
    nie na uczciwość porównania - oba algorytmy dostają te same dane.
    """
    return [
        SyntheticSubmission(
            experience_level=rng.choice(list(ExperienceLevel)),
            preferred_role=rng.choice(list(PreferredRole)),
            skills=rng.sample(SKILL_POOL, rng.randint(1, 3)),
            availability=rng.random() < 0.8,
        )
        for _ in range(count)
    ]


def compare_algorithms(
    candidate: Algorithm,
    baseline: Algorithm,
    *,
    datasets: int,
    seed: int,
) -> list[MeasureComparison]:
    """Porównuje dwa algorytmy wszystkimi miarami `TeamScore` na `datasets` zestawach.

    Liczba osób (8-40) i limit zespołu (3-5) też są losowane, żeby wynik nie
    zależał od jednego wygodnego przypadku. Dla danego `seed` wynik jest
    zawsze ten sam.
    """
    if datasets < 1:
        raise ValueError("Porównanie wymaga co najmniej jednego zestawu danych.")

    rng = random.Random(seed)
    candidate_scores: list[TeamScore] = []
    baseline_scores: list[TeamScore] = []
    for _ in range(datasets):
        people = synthetic_submissions(rng, rng.randint(8, 40))
        team_size = rng.randint(3, 5)
        run_seed = rng.randrange(2**32)
        # Każdy algorytm dostaje własną kopię listy, żeby żaden nie mógł
        # przestawić danych drugiemu.
        candidate_scores.append(
            score_teams(candidate(list(people), team_size, rng=random.Random(run_seed)))
        )
        baseline_scores.append(
            score_teams(baseline(list(people), team_size, rng=random.Random(run_seed)))
        )

    comparisons = []
    for measure in fields(TeamScore):
        ours = [getattr(score, measure.name) for score in candidate_scores]
        theirs = [getattr(score, measure.name) for score in baseline_scores]
        pairs = list(zip(ours, theirs, strict=True))
        comparisons.append(
            MeasureComparison(
                measure=measure.name,
                candidate_mean=sum(ours) / datasets,
                baseline_mean=sum(theirs) / datasets,
                better=sum(1 for mine, other in pairs if mine < other),
                ties=sum(1 for mine, other in pairs if mine == other),
                worse=sum(1 for mine, other in pairs if mine > other),
            )
        )
    return comparisons


def format_table(
    comparisons: list[MeasureComparison],
    *,
    candidate_name: str = "balanced",
    baseline_name: str = "random",
) -> str:
    """Tabela do konsoli: jedna miara w wierszu, niżej = lepiej."""
    header = (
        f"{'miara (nizej = lepiej)':40} {baseline_name:>12} {candidate_name:>12}"
        f"   {candidate_name} lepszy / remis / gorszy"
    )
    rows = [
        f"{LABELS[c.measure]:40} {c.baseline_mean:12.2f} {c.candidate_mean:12.2f}"
        f"   {c.better:>5} / {c.ties:>5} / {c.worse:>5}"
        for c in comparisons
    ]
    return "\n".join([header, *rows])


def _positive_int(value: str) -> int:
    # Własny komunikat także dla "abc": domyślny błąd argparse pokazałby nazwę
    # tej funkcji ("invalid _positive_int value"), która nic nie mówi.
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("musi byc liczba dodatnia") from None
    if number < 1:
        raise argparse.ArgumentTypeError("musi byc liczba dodatnia")
    return number


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        # Bez `prog` pomoc podpowiadałaby "compare.py", a uruchomiony tak plik
        # nie znajdzie pakietu `app` - działa tylko `python -m`.
        prog="python -m app.matching.compare",
        description="Porownanie balanced_teams z random_teams na losowych danych (#26).",
    )
    parser.add_argument(
        "--datasets", type=_positive_int, default=300, help="liczba zestawow (domyslnie 300)"
    )
    parser.add_argument("--seed", type=int, default=2026, help="ziarno generatora (domyslnie 2026)")
    args = parser.parse_args(argv)

    comparisons = compare_algorithms(
        balanced_teams, random_teams, datasets=args.datasets, seed=args.seed
    )
    print(
        f"{args.datasets} zestawow, ziarno {args.seed}. "
        "Nizej = lepiej (kierunek miary f czeka na #58).\n"
    )
    print(format_table(comparisons))


if __name__ == "__main__":
    main()
