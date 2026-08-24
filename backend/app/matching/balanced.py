"""Dopasowanie uwzględniające profil uczestnika: poziom i rola.

Baseline (`baseline.random_teams`) tasuje listę i tnie ją na kawałki - może
z tego wyjść zespół samych początkujących albo pięciu frontendowców bez nikogo
od backendu. Ten moduł rozwiązuje to samo zadanie w trzech krokach, świadomie
rozdzielonych, bo każdy z nich optymalizuje co innego:

1. **Puste zespoły** - ile zespołów i jakiej wielkości. Kryterium: nikt nie
   przekracza limitu, rozmiary różnią się najwyżej o jedną osobę. To dokładnie
   to, co robi `baseline.team_sizes`, więc go tu używamy zamiast pisać drugi raz.
2. **Rozstawienie poziomów** - które miejsce w którym zespole ma być
   "zaawansowany", a które "początkujący". Kryterium: suma punktów za
   doświadczenie (zaawansowany 3, średniozaawansowany 2, początkujący 1) ma być
   w każdym zespole jak najbardziej zbliżona.
3. **Wybór konkretnych osób** - na miejsce o danym poziomie trafia ten kandydat,
   który najbardziej uzupełnia zespół. Kryterium: różnorodność ról (nie dwóch
   frontendowców, gdy czeka backendowiec), a przy remisie - mniejsze pokrycie
   umiejętności, które w zespole już są.

Rozdzielenie kroku 2 od 3 jest tu istotne: gdyby wybierać ludzi "od razu",
optymalizacja ról psułaby rozkład doświadczenia (wzięlibyśmy backendowca-
-początkującego tam, gdzie potrzebny był zaawansowany). W tej kolejności rola
rozstrzyga tylko *między osobami o tym samym poziomie*, więc balans
doświadczenia z kroku 2 zostaje nienaruszony.

Funkcja jest czysta - bez bazy i bez HTTP, dostaje listę i zwraca listę list.
Pełny opis kryteriów i gwarancji: [README.md](README.md).
"""

import random
from collections import Counter
from typing import Protocol

from app.enums import ExperienceLevel, PreferredRole
from app.matching.baseline import team_sizes

# Punkty za poziom doświadczenia - "waluta", w której krok 2 wyrównuje zespoły.
# Skala 1/2/3 jest liniowa i celowo prosta: nie twierdzimy, że zaawansowany jest
# dokładnie trzy razy lepszy od początkującego, chodzi tylko o to, żeby zespół
# złożony z samych początkujących był wyraźnie "lżejszy" od mieszanego.
#
# `None` (zgłoszenia sprzed rozszerzenia modelu, patrz `Submission`) dostaje 0.
# Brak danych traktujemy pesymistycznie - nie doliczamy zespołowi doświadczenia,
# którego nie umiemy potwierdzić, więc taki zespół dostanie na wyrównanie kogoś
# o znanym, wyższym poziomie. Odwrotne założenie (liczyć jak średni poziom)
# mogłoby po cichu zbudować zespół z samych niewiadomych.
EXPERIENCE_POINTS: dict[ExperienceLevel | None, int] = {
    None: 0,
    ExperienceLevel.BEGINNER: 1,
    ExperienceLevel.INTERMEDIATE: 2,
    ExperienceLevel.ADVANCED: 3,
}


class Participant(Protocol):
    """Minimum, którego algorytm potrzebuje od zgłoszenia.

    Protokół zamiast `Submission`, bo ta logika nie ma nic wspólnego z bazą:
    testy podstawiają zwykłą dataclass, a produkcyjnie wchodzi model ORM.
    Wystarczy, że obiekt ma te trzy pola - nie musi niczego dziedziczyć.
    """

    experience_level: ExperienceLevel | None
    preferred_role: PreferredRole | None
    skills: list[str]


def experience_points(participant: Participant) -> int:
    """Punkty za doświadczenie jednego uczestnika (patrz `EXPERIENCE_POINTS`)."""
    return EXPERIENCE_POINTS.get(participant.experience_level, 0)


def team_experience_points(team: list[Participant]) -> int:
    """Suma punktów zespołu - miara, którą krok 2 wyrównuje między zespołami.

    Wyciągnięta na zewnątrz, bo przydaje się też testom i przyszłej metryce
    jakości dopasowania (#26) do porównywania algorytmów na tych samych danych.
    """
    return sum(experience_points(member) for member in team)


def _plan_experience_slots(
    sizes: list[int],
    levels: list[ExperienceLevel | None],
) -> list[list[ExperienceLevel | None]]:
    """Krok 2: rozstawia poziomy po pustych miejscach w zespołach.

    Dostaje rozmiary zespołów i worek poziomów (dokładnie tych, które zgłosili
    uczestnicy), a zwraca dla każdego zespołu listę poziomów, jakie mają w nim
    zająć miejsca. Nie wie jeszcze, kto konkretnie je zajmie - to krok 3.

    Heurystyka: bierzemy poziomy od najmocniejszego i każdy dokładamy do
    zespołu z najniższą dotychczasową sumą punktów (spośród tych, które mają
    jeszcze wolne miejsce). To klasyczne zachłanne wyrównywanie obciążenia -
    najpierw rozdajemy to, co waży najwięcej, bo późniejsze drobiazgi łatwiej
    dopasują resztę. Efekt uboczny, na którym nam zależy: pierwsze `N` osób
    o wyższym poziomie trafia do `N` *różnych* zespołów (zespół po dostaniu
    kogokolwiek ma już sumę > 0, więc przestaje być najuboższy), czyli żaden
    zespół nie kończy jako "sami początkujący", o ile input na to pozwala.

    Remisy rozstrzygamy najpierw na korzyść zespołu z większą liczbą wolnych
    miejsc: większy zespół potrzebuje więcej materiału na wyrównanie, a gdyby
    został z samymi resztkami na koniec, wyszedłby najsłabszy. Ostatnie
    kryterium (indeks) daje powtarzalny wynik zamiast zależnego od kolejności
    słownika.
    """
    slots: list[list[ExperienceLevel | None]] = [[] for _ in sizes]
    points = [0 for _ in sizes]
    free = list(sizes)

    for level in sorted(levels, key=lambda item: EXPERIENCE_POINTS.get(item, 0), reverse=True):
        team_index = min(
            (index for index, remaining in enumerate(free) if remaining > 0),
            key=lambda index: (points[index], -free[index], index),
        )
        slots[team_index].append(level)
        points[team_index] += EXPERIENCE_POINTS.get(level, 0)
        free[team_index] -= 1

    return slots


def _best_candidate_index(candidates: list[Participant], team: list[Participant]) -> int:
    """Krok 3: który z kandydatów o *tym samym* poziomie pasuje tu najlepiej.

    Wszyscy kandydaci mają ten sam poziom doświadczenia, więc wybór nie rusza
    balansu z kroku 2 - decyduje wyłącznie to, czego zespołowi brakuje:

    1. **Rola** - ile osób w zespole ma już tę samą preferowaną rolę. Zero bije
       jedynkę, więc przy wyborze między frontendowcem a backendowcem do zespołu,
       w którym jest już frontendowiec, wejdzie backendowiec (przykład z issue).
    2. **Umiejętności** - ile umiejętności kandydata zespół już zna. Mniej
       pokrycia to szerszy zespół; to kryterium rozstrzyga remisy w rolach
       (np. dwóch backendowców, jeden zna to samo co reszta, drugi coś nowego).
    3. **Kolejność** - ostateczny rozjemca, żeby wynik był powtarzalny.

    Zwracamy indeks, a nie samego kandydata, bo wywołujący musi go usunąć
    z puli - ta sama osoba nie może trafić do dwóch zespołów.
    """
    taken_roles = Counter(member.preferred_role for member in team)
    known_skills = {skill for member in team for skill in member.skills}

    return min(
        range(len(candidates)),
        key=lambda index: (
            taken_roles[candidates[index].preferred_role],
            len(known_skills.intersection(candidates[index].skills)),
            index,
        ),
    )


# `[T: Participant]`: funkcja czyta pola opisane protokołem, ale zwraca dokładnie
# ten typ, który dostała - `list[Submission]` na wejściu daje
# `list[list[Submission]]` na wyjściu, a nie `list[list[Participant]]`.
def balanced_teams[T: Participant](
    submissions: list[T],
    team_size: int,
    *,
    rng: random.Random | None = None,
) -> list[list[T]]:
    """Dzieli zgłoszenia na zespoły wyrównane pod względem poziomu i ról.

    Gwarancje (te same, co w baseline, plus dwie nowe):

    - każde zgłoszenie trafia do dokładnie jednego zespołu,
    - żaden zespół nie przekracza `team_size` i żaden nie jest pusty,
    - rozmiary zespołów różnią się najwyżej o jedną osobę,
    - sumy punktów za doświadczenie są wyrównywane zachłannie, a gdy osób
      o poziomie wyższym niż początkujący jest co najmniej tyle, ile zespołów,
      każdy zespół dostaje przynajmniej jedną taką osobę,
    - przy równym poziomie preferowana jest osoba o roli, której w zespole
      jeszcze nie ma.

    To heurystyka, nie optymalizacja dokładna: idealne wyrównanie sum punktów
    to problem NP-trudny (podział zbioru), a przy kilkudziesięciu zgłoszeniach
    zachłanny wynik jest wystarczająco dobry i liczy się w ułamku sekundy.

    `rng` jest opcjonalny i - inaczej niż w baseline - nie służy do losowania
    składów. Miesza tylko kolejność wejścia, czyli zmienia sposób rozstrzygania
    remisów; wszystkie gwarancje wyżej obowiązują tak samo. Bez `rng` funkcja
    jest w pełni deterministyczna: te same zgłoszenia dają ten sam podział, co
    pozwala porównywać algorytmy na tych samych danych.

    Wejściowa lista zostaje nietknięta; zwracana jest nowa.

    Rzuca `ValueError`, gdy `team_size` jest mniejszy niż 1 (walidacja
    w `team_sizes` - patrz SECURITY.md, wejścia sprawdzamy zawsze).
    """
    # Kopia: `shuffle` przestawia elementy w miejscu, a funkcja ma być czysta.
    participants = list(submissions)
    if rng is not None:
        rng.shuffle(participants)

    # Krok 1: same "szablony" zespołów - na razie tylko ich liczba i rozmiary.
    sizes = team_sizes(len(participants), team_size)
    if not sizes:
        return []

    # Krok 2: które miejsce w którym zespole ma jaki poziom doświadczenia.
    slots = _plan_experience_slots(sizes, [person.experience_level for person in participants])

    # Pula kandydatów rozbita na poziomy - krok 3 wybiera zawsze w obrębie
    # jednego poziomu, więc taki podział oszczędza filtrowania przy każdym
    # miejscu. Kolejność w każdej puli to kolejność wejścia (patrz `rng`).
    pool: dict[ExperienceLevel | None, list[T]] = {}
    for person in participants:
        pool.setdefault(person.experience_level, []).append(person)

    teams: list[list[T]] = [[] for _ in sizes]

    # Krok 3: obsadzamy miejsca rundami - najpierw pierwsze miejsce każdego
    # zespołu, potem drugie itd. Gdyby kompletować zespoły po kolei, pierwszy
    # wybierałby z pełnej puli, a ostatni brał to, co zostało; rundy dają
    # wszystkim zespołom podobne pole manewru przy doborze ról.
    for round_index in range(max(sizes)):
        for team_index, team_slots in enumerate(slots):
            if round_index >= len(team_slots):
                continue

            candidates = pool[team_slots[round_index]]
            chosen = candidates.pop(_best_candidate_index(candidates, teams[team_index]))
            teams[team_index].append(chosen)

    return teams
