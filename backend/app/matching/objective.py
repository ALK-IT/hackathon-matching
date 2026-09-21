"""Funkcja celu: jedna liczba mówiąca, jak dobry jest układ zespołów.

Wydzielone z `balanced.py` (#116). Najniższa warstwa pakietu - nie wie nic
o tym, JAK powstaje podział, umie tylko ocenić gotowy. Dzięki temu korzystają
z niej zarówno sam algorytm (`balanced.py`), naprawa wymianami (`repair.py`),
jak i metryka porównująca warianty (`metrics.py`, #26) - a porównanie mierzy
dokładnie to, co optymalizuje algorytm.

Mieszka tu też protokół `Participant`, bo to on definiuje minimum, którego
ocena potrzebuje od zgłoszenia. Wszystko pozostałe w pakiecie buduje na nim,
więc trzymanie go piętro wyżej oznaczałoby import w drugą stronę.
"""

from typing import Protocol

from app.enums import ExperienceLevel, PreferredRole

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
