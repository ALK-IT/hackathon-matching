"""Metryka jakości dopasowania - ocena gotowego podziału na zespoły (#26).

Odpowiada na pytanie z issue: skąd wiadomo, że `balanced_teams` dzieli lepiej
niż `random_teams`? `score_teams` ocenia podział zestawem nazwanych miar
w jednostkach, które da się przeczytać ("punkty", "% zespołów"). Ich wartość
polega na tym, że pokazują, CO się poprawiło, a co nie - jedna liczba by to
ukryła.

Zasada czytania: w każdej mierze niżej = lepiej. Wyjątkiem jest
`availability_spread`, której kierunek czeka na decyzję w #58 (komentarz przy
polu).

Czytając porównanie, trzeba wiedzieć, które miary są niezależne od algorytmu:
- `experience_spread`, `role_spread` i `duplicate_skills_per_team` to rozpisane
  na jednostki składniki `objective`. `balanced_teams` optymalizuje je wprost,
  więc przewaga w nich pokazuje, że algorytm robi to, co ma robić, a nie że
  jest lepszy według jakiegoś zewnętrznego kryterium;
- `teams_without_*_pct` zależą od rozkładu ról tylko pośrednio, a
  `teams_without_experienced_pct` pilnuje gwarancja z #24 - `objective` żadnej
  z nich nie liczy;
- `availability_spread` jest dziś od algorytmu całkiem niezależna (#58);
- `size_spread` jest kontrolna.

Liczba zbiorcza to świadomie istniejące `objective` z `balanced.py`, a nie
nowa formuła z wymyślonymi wagami. `balanced_teams` optymalizuje ją
heurystycznie, więc prawie zawsze w niej wygrywa - i ta wygrana sama niczego
nie dowodzi.

Porównanie algorytmów na wielu zestawach danych: `python -m app.matching.compare`.
"""

from dataclasses import dataclass
from typing import Protocol

from app.enums import ExperienceLevel, PreferredRole
from app.matching.objective import (
    EXPERIENCE_POINTS,
    Participant,
    experience_points,
    objective,
    team_experience_points,
)

# Próg "doświadczonej" osoby: co najmniej średniozaawansowany. Ten sam, na
# którym stoi gwarancja z #24 ("żaden zespół z samych początkujących").
_EXPERIENCED_POINTS = EXPERIENCE_POINTS[ExperienceLevel.INTERMEDIATE]


class ScoredParticipant(Participant, Protocol):
    """To, czego metryka potrzebuje od zgłoszenia: profil jak w algorytmie
    plus dostępność, której sam algorytm (jeszcze) nie czyta."""

    availability: bool


@dataclass(frozen=True)
class TeamScore:
    """Ocena jednego podziału na zespoły. W każdym polu niżej = lepiej
    (poza `availability_spread`, której kierunek czeka na #58)."""

    # a) Różnica sum punktów za doświadczenie (max - min) między zespołami.
    #    Główne kryterium algorytmu: 0 znaczy idealnie równe zespoły.
    experience_spread: int

    # b1/b2) Jaki odsetek zespołów nie ma nikogo z daną rolą. `fullstack` nie
    #    liczy się tu jako backend ani frontend - tak samo jak w algorytmie
    #    (zmianę proponuje #76). Wartość zależy też od danych: gdy backendowców
    #    jest mniej niż zespołów, część zespołów musi zostać bez nich, więc tę
    #    miarę czyta się względem innego algorytmu na tych samych danych.
    teams_without_backend_pct: float
    teams_without_frontend_pct: float

    # b3) Średnio po rolach: o ile różni się liczba osób z daną rolą między
    #    zespołem, w którym jest ich najwięcej, a tym, w którym najmniej. Brak
    #    roli (None) to brak danych, nie rola - nie wchodzi do średniej, tak
    #    jak w `objective`.
    role_spread: float

    # c) Średnio na zespół: ile razy umiejętność powtarza się w składzie
    #    (wystąpienia minus różne). Mniej powtórzeń = szersze pokrycie.
    duplicate_skills_per_team: float

    # d) Różnica wielkości zespołów (max - min). Miara KONTROLNA: oba algorytmy
    #    dzielą według `team_sizes`, więc wychodzi zawsze tak samo (0 albo 1).
    #    Różnica między algorytmami oznaczałaby błąd, a nie lepszy podział.
    size_spread: int

    # e) Odsetek zespołów bez nikogo co najmniej średniozaawansowanego
    #    (sami początkujący albo osoby bez podanego poziomu).
    teams_without_experienced_pct: float

    # f) Różnica liczby osób bez pełnej dostępności (`availability=False`)
    #    między zespołami (max - min). Kierunek NIE jest przesądzony: treść #58
    #    mówi o zrównoważeniu takich osób (wtedy niżej = lepiej), a komentarz
    #    przy kolumnie `availability` w models.py - o ich grupowaniu. Jeśli #58
    #    wybierze grupowanie, potrzebna będzie inna miara (np. w ilu zespołach
    #    jest ktokolwiek bez pełnej dostępności), bo sama zmiana znaku nie
    #    odróżni pełnego zgrupowania [4, 4, 0, 0] od częściowego [4, 2, 2, 0].
    availability_spread: int

    # Liczba zbiorcza: funkcja celu algorytmu (patrz docstring modułu).
    objective: int


def _spread(values: list[int]) -> int:
    return max(values) - min(values)


def _percent_of(teams: list[list[ScoredParticipant]], matching: int) -> float:
    return 100 * matching / len(teams)


def score_teams(teams: list[list[ScoredParticipant]]) -> TeamScore:
    """Ocenia gotowy podział na zespoły wszystkimi miarami naraz.

    Funkcja jest czysta - bez bazy i bez HTTP - i przyjmuje wynik dowolnego
    algorytmu, więc da się nią porównać każde dwa podziały tych samych osób.
    Pusta lista zespołów daje same zera: nie ma czego oceniać.
    """
    if not teams:
        return TeamScore(0, 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0, 0)

    def has_role(team: list[ScoredParticipant], role: PreferredRole) -> bool:
        return any(member.preferred_role == role for member in team)

    role_spreads = [
        _spread([sum(1 for member in team if member.preferred_role == role) for team in teams])
        for role in PreferredRole
    ]
    duplicates = sum(
        sum(len(member.skills) for member in team)
        - len({skill for member in team for skill in member.skills})
        for team in teams
    )

    return TeamScore(
        experience_spread=_spread([team_experience_points(team) for team in teams]),
        teams_without_backend_pct=_percent_of(
            teams, sum(1 for team in teams if not has_role(team, PreferredRole.BACKEND))
        ),
        teams_without_frontend_pct=_percent_of(
            teams, sum(1 for team in teams if not has_role(team, PreferredRole.FRONTEND))
        ),
        role_spread=sum(role_spreads) / len(role_spreads),
        duplicate_skills_per_team=duplicates / len(teams),
        size_spread=_spread([len(team) for team in teams]),
        teams_without_experienced_pct=_percent_of(
            teams,
            sum(
                1
                for team in teams
                if all(experience_points(member) < _EXPERIENCED_POINTS for member in team)
            ),
        ),
        availability_spread=_spread(
            [sum(1 for member in team if not member.availability) for team in teams]
        ),
        objective=objective(teams),
    )
