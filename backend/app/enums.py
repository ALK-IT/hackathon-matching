from enum import StrEnum


class ExperienceLevel(StrEnum):
    """Poziom doświadczenia uczestnika.

    Skala jest celowo trzystopniowa i uporządkowana od najniższego poziomu:
    algorytm dopasowania (#23) ma na jej podstawie rozkładać doświadczenie
    równomiernie między zespoły, a nie tylko porównywać etykiety.
    """

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class PreferredRole(StrEnum):
    """Rola, w której uczestnik chce pracować w zespole.

    Zbiór jest zamknięty, bo dopasowanie musi móc powiedzieć "w tym zespole
    brakuje frontendowca" - przy dowolnym tekście od uczestnika ("front",
    "React dev", "przód") nie da się tego policzyć bez zgadywania.

    `OTHER` jest wentylem bezpieczeństwa dla osób, które nie mieszczą się
    w powyższych kategoriach - bez niego musiałyby wybrać rolę na chybił
    trafił i zafałszować dane wejściowe algorytmu.
    """

    FRONTEND = "frontend"
    BACKEND = "backend"
    FULLSTACK = "fullstack"
    DESIGN = "design"
    DATA = "data"
    PM = "pm"
    OTHER = "other"
