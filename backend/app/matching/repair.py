"""Krok 4 algorytmu: naprawa gotowego układu wymianami par.

Wydzielone z `balanced.py` (#116). Osobny moduł, bo to jedyna część algorytmu,
która ogląda CAŁY układ naraz i cofa decyzje podjęte wcześniej - kroki 1-3
sadzają ludzi po kolei i nigdy nie wracają. Tu też trafi rozszerzenie
o rotacje trzyosobowe (#79).

`_swap_repair` zachowuje podkreślenie mimo importu spoza modułu: nazwa jest
prywatna dla PAKIETU `app/matching/`, a nie dla pliku. Poza pakietem nikt jej
nie woła - wejściem jest `balanced_teams`.
"""

from app.matching.objective import Participant, experience_points, objective

_MAX_REPAIR_PASSES = 8

# Budżet pracy naprawy wymianami, w jednostkach "ewaluacja objective × liczba
# uczestników". Zmierzone (siatka syntetyczna, ten sam kod): ~1 mln jednostek
# na sekundę, więc 3 mln to twardy sufit ~3 s niezależnie od liczby zgłoszeń.
# Do ~120 uczestników pełna zbieżność mieści się w budżecie - wynik jest
# bitowo identyczny jak bez limitu; powyżej naprawa kończy się częściowa,
# co jest łagodne: pierwsze wymiany dają największe zyski, a wszystkie twarde
# gwarancje pochodzą z faz 1-3. Jednostki pracy zamiast sekund, bo limit
# czasowy łamałby determinizm (ten sam input różne wyniki pod obciążeniem).
_MAX_REPAIR_WORK = 3_000_000


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

    participant_count = len(people)
    work = 0

    # `current` przeliczane tylko po zaakceptowanej zamianie, nie dla każdego
    # kandydata - to zbija koszt skanu o połowę bez zmiany wyniku.
    current = objective(teams)
    for _ in range(_MAX_REPAIR_PASSES):
        improved = False
        for i in range(len(teams)):
            for j in range(i + 1, len(teams)):
                for a in range(len(teams[i])):
                    for b in range(len(teams[j])):
                        # Budżet pracy (#57): koszt jednej ewaluacji rośnie
                        # liniowo z liczbą uczestników, stąd taka jednostka.
                        # Naliczamy PRZED próbą, więc płacą też kandydaci
                        # odrzuceni przez strażnika - budżet jest górnym
                        # oszacowaniem pracy, celowo konserwatywnym.
                        # Wyjście w środku skanu jest bezpieczne - dotychczas
                        # przyjęte zamiany zostają, układ jest poprawny.
                        work += participant_count
                        if work > _MAX_REPAIR_WORK:
                            return teams
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
