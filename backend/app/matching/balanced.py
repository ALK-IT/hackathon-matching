"""Dopasowanie uwzględniające profil uczestnika: poziom i rola.

Baseline (`baseline.random_teams`) tasuje listę i tnie ją na kawałki - może
z tego wyjść zespół samych początkujących albo pięciu frontendowców bez nikogo
od backendu. Ten moduł rozwiązuje to samo zadanie w czterech krokach, świadomie
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
4. **Naprawa wymianami** - przegląd gotowego układu: zamiany par uczestników
   między zespołami zostają, gdy obniżają jawną funkcję celu (`objective`)
   i nie łamią gwarancji nie-beginnera. Kroki 1-3 decydują po jednej osobie
   i nie wracają do wcześniejszych decyzji - naprawa widzi całość i domyka to,
   czego zachłanny przebieg nie mógł przewidzieć.

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


# Wagi funkcji celu. Rozpiętości mnożone są tak, żeby hierarchia kryteriów była
# w praktyce ścisła: jedna jednostka doświadczenia przebija każdą realną sumę
# kar za role, a jednostka ról - kary za umiejętności. Zapas jest duży (100x)
# przy skali hackathonu; przy tysiącach zgłoszeń wagi wymagałyby rewizji.
_EXPERIENCE_WEIGHT = 100_000
_ROLE_WEIGHT = 1_000
_SKILL_WEIGHT = 1

_MAX_REPAIR_PASSES = 8


def objective(teams: list[list[Participant]]) -> int:
    """Ocena całego układu zespołów - niższa jest lepsza.

    Składniki, zgodnie z hierarchią kryteriów modułu:
    - rozpiętość sum punktów doświadczenia (max - min między zespołami),
    - dla każdej zadeklarowanej roli: rozpiętość liczebności między zespołami
      (None to brak danych, nie rola - bez kary za jego skupienie),
    - powtórzenia umiejętności w zespołach (wystąpienia minus różne,
      sumowane po zespołach).

    To ta sama funkcja, którą optymalizuje krok 4 (naprawa wymianami) - #26
    może jej użyć jako punktu wyjścia do porównywania algorytmów, wtedy
    optymalizujemy dokładnie to, co mierzymy.
    """
    if not teams:
        return 0

    sums = [team_experience_points(team) for team in teams]
    score = _EXPERIENCE_WEIGHT * (max(sums) - min(sums))

    for role in PreferredRole:
        counts = [sum(1 for member in team if member.preferred_role == role) for team in teams]
        score += _ROLE_WEIGHT * (max(counts) - min(counts))

    for team in teams:
        mentions = sum(len(member.skills) for member in team)
        distinct = len({skill for member in team for skill in member.skills})
        score += _SKILL_WEIGHT * (mentions - distinct)

    return score


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


def _swap_repair[T: Participant](teams: list[list[T]]) -> list[list[T]]:
    """Krok 4: wymiany par między zespołami, dopóki obniżają `objective`.

    Kroki 1-3 sadzają ludzi po kolei i nie wracają do podjętych decyzji -
    ostatnie miejsca nie mają już wyboru. Naprawa patrzy na skończony układ
    i przyjmuje każdą zamianę 1-za-1, która ściśle obniża wynik; rozmiary
    zespołów nie mogą się przy tym zepsuć z konstrukcji.

    Strażnik: zamiana łamiąca gwarancję nie-beginnera jest odrzucana nawet
    przy lepszym wyniku. Stała kolejność skanu i stałe kryterium akceptacji
    dają deterministyczny wynik. Limit przejść domyka czas przy patologiach;
    w praktyce zbieżność następuje po 2-3 przejściach.
    """
    people = [member for team in teams for member in team]
    non_beginners = sum(1 for member in people if experience_points(member) >= 2)
    guarantee_applies = non_beginners >= len(teams)

    def guarantee_holds() -> bool:
        if not guarantee_applies:
            return True
        return all(any(experience_points(member) >= 2 for member in team) for team in teams)

    # `current` przeliczane tylko po zaakceptowanej zamianie, nie dla każdego
    # kandydata - to zbija koszt skanu o połowę bez zmiany wyniku.
    current = objective(teams)
    for _ in range(_MAX_REPAIR_PASSES):
        improved = False
        for i in range(len(teams)):
            for j in range(i + 1, len(teams)):
                for a in range(len(teams[i])):
                    for b in range(len(teams[j])):
                        teams[i][a], teams[j][b] = teams[j][b], teams[i][a]
                        candidate = objective(teams)
                        if candidate < current and guarantee_holds():
                            current = candidate
                            improved = True
                        else:
                            teams[i][a], teams[j][b] = teams[j][b], teams[i][a]
        if not improved:
            break

    return teams


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
      jeszcze nie ma,
    - gotowy układ przechodzi naprawę wymianami (krok 4): zostają wyłącznie
      zamiany ściśle obniżające `objective`, a zamiana łamiąca gwarancję
      nie-beginnera jest odrzucana nawet przy lepszym wyniku.

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

    # Krok 4: naprawa wymianami - szczegóły w docstringu `_swap_repair` i README.
    return _swap_repair(teams)
