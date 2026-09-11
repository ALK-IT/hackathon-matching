"""Zakłada konto organizatora (SPEC-005, #119).

Uruchomienie, z katalogu `backend/`:

    python -m scripts.create_organizer

Dlaczego skrypt, a nie endpoint: konto administratora ma móc założyć wyłącznie
ktoś z dostępem do serwera. Endpoint rejestracji byłby najkrótszą drogą do tego,
żeby uczestnik hackathonu założył sobie konto organizatora - a model zagrożenia
ze SPEC-005 zakłada dokładnie takiego przeciwnika.

Hasło nie jest przyjmowane argumentem wiersza poleceń ani ze zmiennej
środowiskowej. Argumenty widać w `ps` u każdego użytkownika maszyny i zostają
w historii powłoki, a zmienne środowiskowe wyciekają do logów i raportów
o błędach. Jedyne wejście to `getpass`, czyli odczyt bez echa na terminalu.
"""

import asyncio
import sys
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Organizer
from app.schemas import OrganizerEmail
from app.security import WeakPasswordError, hash_password, validate_password_strength


def _read_email() -> str:
    """Pyta o adres i sprowadza go do postaci, którą przyjmie baza.

    Ta sama walidacja co dla zgłoszeń uczestników (`OrganizerEmail`), bo konto
    założone na adres niespełniający reguł API byłoby kontem, którym nie da się
    zalogować - błąd wyszedłby dopiero przy pierwszym logowaniu.
    """
    raw = input("E-mail organizatora: ")
    try:
        return str(OrganizerEmail(email=raw).email)
    except ValidationError:
        print("To nie jest poprawny adres e-mail.", file=sys.stderr)
        raise SystemExit(1) from None


def _read_password() -> str:
    """Pyta o hasło dwukrotnie i sprawdza politykę przed zahashowaniem.

    Powtórzenie nie jest formalnością: hasła nie widać przy wpisywaniu, a przy
    literówce nie ma jak jej wykryć później - w bazie jest tylko hash, więc
    właściciel konta zostałby zablokowany bez żadnej diagnostyki.
    """
    password = getpass("Hasło (nie będzie widoczne): ")

    try:
        validate_password_strength(password)
    except WeakPasswordError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None

    if password != getpass("Powtórz hasło: "):
        print("Hasła nie są identyczne.", file=sys.stderr)
        raise SystemExit(1)

    return password


async def _create(email: str, password_hash: str) -> None:
    """Zapisuje konto; przerywa, jeśli takie już istnieje.

    Sprawdzenie przed zapisem daje czytelny komunikat, ale nie jest jedyną
    ochroną - między odczytem a zapisem ktoś mógłby założyć to samo konto,
    więc łapiemy też `IntegrityError` z ograniczenia unikalności. To baza jest
    tu ostateczną instancją, nie skrypt.
    """
    async with SessionLocal() as session:
        existing = await session.execute(select(Organizer).where(Organizer.email == email))
        if existing.scalar_one_or_none() is not None:
            print(f"Konto {email} już istnieje.", file=sys.stderr)
            raise SystemExit(1)

        session.add(Organizer(email=email, password_hash=password_hash))
        try:
            await session.commit()
        except IntegrityError:
            print(f"Konto {email} już istnieje.", file=sys.stderr)
            raise SystemExit(1) from None


def main() -> None:
    email = _read_email()
    password = _read_password()

    # Hashujemy przed wejściem do bazy, żeby hasło w postaci jawnej żyło
    # w pamięci możliwie krótko i nie trafiło do żadnej warstwy zapisu.
    password_hash = hash_password(password)

    asyncio.run(_create(email, password_hash))

    # Świadomie bez echa adresu w jednej linii z czymkolwiek, co przypomina
    # hasło - ten komunikat bywa wklejany do zgłoszeń i czatów zespołu.
    print(f"Konto organizatora {email} zostało założone.")


if __name__ == "__main__":
    main()
