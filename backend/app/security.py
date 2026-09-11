"""Hashowanie haseł organizatorów i polityka ich siły (SPEC-005).

Cała wiedza o tym, jak zamieniamy hasło na hash i co uznajemy za hasło zbyt
słabe, siedzi w jednym module. Rozsypana po skrypcie zakładającym konto
i po serwisie logowania rozjechałaby się przy pierwszej zmianie wymagań.
"""

from pwdlib import PasswordHash

# `recommended()` zamiast ręcznego wyboru algorytmu i parametrów: dziś daje
# argon2id z nastawami, które biblioteka uznaje za rozsądne, a przy aktualizacji
# zależności zmieni się razem z nią. Własne parametry trzeba by pilnować ręcznie
# przez lata, a kryptografia to ostatnie miejsce, w którym chcemy mieć własne
# zdanie bez powodu.
_hasher = PasswordHash.recommended()

# Minimum z SPEC-005. Dwanaście znaków, bo model zagrożenia zakłada atakującego
# obeznanego technicznie: ośmioznakowe hasło pada offline w rozsądnym czasie,
# a limit prób logowania (#120) chroni tylko przed zgadywaniem przez sieć - nie
# pomoże, jeśli kiedykolwiek wycieknie sama tabela z hashami.
PASSWORD_MIN_LENGTH = 12

# Hasła odrzucane niezależnie od długości. Lista jest krótka i celowo nie udaje
# pełnego słownika - ma zatrzymać dokładnie te warianty, które przy tym projekcie
# ktoś wpisze z rozpędu, wliczając "hackathonmatching123", spełniające limit
# dwunastu znaków. Prawdziwą obroną jest długość, to jest zabezpieczenie przed
# odruchem.
_WEAK_FRAGMENTS = frozenset(
    {
        "admin",
        "haslo",
        "hasło",
        "password",
        "hackathon",
        "matching",
        "organizator",
        "qwerty",
        "12345678",
    }
)


class WeakPasswordError(ValueError):
    """Hasło nie spełnia polityki - komunikat w treści wyjątku jest dla człowieka."""


def validate_password_strength(password: str) -> None:
    """Sprawdza hasło przed zahashowaniem; przy odrzuceniu rzuca wyjątek.

    Rzuca, a nie zwraca `bool`, bo wywołujący musi powiedzieć użytkownikowi
    KTÓRA reguła nie przeszła. Zwrócone `False` zmusiłoby skrypt do zgadywania
    powodu albo do pokazania ogólnika "złe hasło", który przy zakładaniu konta
    jest bezużyteczny.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        raise WeakPasswordError(
            f"Hasło musi mieć co najmniej {PASSWORD_MIN_LENGTH} znaków "
            f"(podano {len(password)})."
        )

    lowered = password.lower()
    for fragment in _WEAK_FRAGMENTS:
        if fragment in lowered:
            raise WeakPasswordError(
                f"Hasło zawiera zbyt oczywisty fragment: '{fragment}'. Wybierz inne."
            )


def hash_password(password: str) -> str:
    """Zamienia hasło na hash gotowy do zapisania w kolumnie `password_hash`.

    Nie waliduje siły - to osobna decyzja wywołującego (patrz
    `validate_password_strength`). Gdyby hashowanie samo odrzucało słabe hasła,
    nie dałoby się przehashować istniejącego hasła przy zmianie parametrów
    algorytmu, bo stare mogłoby nie spełniać nowej polityki.
    """
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Sprawdza hasło wobec zapisanego hasha.

    Porównanie w czasie niezależnym od tego, jak bardzo hasło jest podobne do
    prawdziwego, zapewnia sama biblioteka - dlatego nigdy nie porównujemy
    hashy operatorem `==`.
    """
    return _hasher.verify(password, password_hash)
