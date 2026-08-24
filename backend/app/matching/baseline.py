"""Baseline dopasowania: losowa kolejność, równy podział na zespoły.

Najprostszy możliwy algorytm - punkt odniesienia, do którego porównamy
kolejne wersje uwzględniające umiejętności, rolę i doświadczenie. Nie
korzysta z bazy ani z API: dostaje listę, zwraca listę list.
"""

import random
from math import ceil


def team_sizes(participant_count: int, team_size: int) -> list[int]:
    """Liczy rozmiary zespołów: jak najmniej zespołów, jak najbardziej równe.

    `team_size` jest **limitem górnym**, a nie docelowym rozmiarem zespołu.
    Najpierw ustalamy minimalną liczbę zespołów, w których wszyscy się
    zmieszczą, a potem rozdzielamy ludzi między nie po równo. Dlatego
    9 osób przy limicie 4 to trzy zespoły po 3, a nie 4 + 4 + 1.

    Reszty z dzielenia nie da się rozłożyć idealnie równo, więc pierwsze
    `remainder` zespołów dostaje o jedną osobę więcej - różnica między
    najmniejszym a największym zespołem to zawsze najwyżej jeden.

    Przykłady (`participant_count`, `team_size` -> wynik):
      9, 4  -> [3, 3, 3]     (trzy równe, zamiast 4+4+1)
      10, 3 -> [3, 3, 2, 2]  (cztery zespoły, zamiast 3+3+3+1)
      2, 4  -> [2]           (mniej osób niż limit - jeden zespół)
      0, 4  -> []            (brak zgłoszeń - brak zespołów)

    Dwie własności, których pilnują testy i na których opiera się reszta
    modułu: żaden zespół nie przekracza `team_size` i żaden nie jest pusty.
    """
    if team_size < 1:
        # Bez tego `ceil(n / 0)` rzuciłby ZeroDivisionError, a ujemny limit
        # dałby ujemną liczbę zespołów i po cichu pustą listę. Wywołujący ma
        # się dowiedzieć, że przekazał bezsensowny parametr (patrz SECURITY.md
        # - dane wejściowe walidujemy zawsze, także te z własnego kodu).
        raise ValueError("Rozmiar zespołu musi wynosić co najmniej 1.")

    if participant_count < 1:
        return []

    team_count = ceil(participant_count / team_size)

    # divmod: `base` to rozmiar minimalny, `remainder` to liczba zespołów,
    # które dostają jedną osobę ponad ten minimalny rozmiar.
    base, remainder = divmod(participant_count, team_count)

    return [base + 1] * remainder + [base] * (team_count - remainder)


# `[T]` w nagłówku: funkcja nie zagląda do środka elementów - tylko je tasuje
# i tnie na kawałki. Dzięki temu testy nie muszą budować modelu SQLAlchemy ani
# łączyć się z bazą, a produkcyjne wywołanie z `list[Submission]` zwróci
# `list[list[Submission]]` z zachowanym typem (a nie `Any`).
def random_teams[T](
    submissions: list[T],
    team_size: int,
    *,
    rng: random.Random | None = None,
) -> list[list[T]]:
    """Dzieli zgłoszenia na zespoły w losowej kolejności.

    Sam podział jest deterministyczny (patrz `team_sizes`) - losowa jest
    tylko kolejność, w jakiej uczestnicy trafiają do kolejnych zespołów.
    Każde zgłoszenie ląduje w dokładnie jednym zespole, żaden zespół nie
    przekracza `team_size` i żaden nie jest pusty.

    `rng` pozwala testom podać własny generator (`random.Random(42)`)
    zamiast ustawiać ziarno globalnego `random`. Globalne ziarno wycieka
    między testami i psuje je w zależności od kolejności uruchomienia;
    własny generator jest lokalny dla jednego wywołania. Produkcyjnie
    parametr się pomija - wtedy działa domyślny `random`.

    Uwaga: `random` to generator do zastosowań niekryptograficznych.
    Tutaj to w porządku - wynik nie chroni niczego, a `secrets` byłby
    wolniejszy i nie dałby powtarzalności potrzebnej w testach.

    Zwracana lista jest nowa; wejściowa `submissions` zostaje nietknięta.
    """
    generator = rng or random

    # Kopia, bo `shuffle` przestawia elementy w miejscu - bez niej funkcja
    # zmieniałaby listę, którą dostała od wywołującego.
    shuffled = list(submissions)
    generator.shuffle(shuffled)

    teams: list[list[T]] = []
    start = 0
    for size in team_sizes(len(shuffled), team_size):
        teams.append(shuffled[start : start + size])
        start += size

    return teams
