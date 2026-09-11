"""Konta organizatorów: hasła, ograniczenia bazy i skrypt zakładający (#119).

Trzy warstwy, bo każda potrafi zawieść osobno: polityka haseł w Pythonie,
ograniczenia w Postgresie (działają też wtedy, gdy ktoś ominie aplikację)
oraz skrypt, który jest jedyną drogą do założenia konta.
"""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.db import DATABASE_URL
from app.schemas import OrganizerEmail
from app.security import (
    PASSWORD_MIN_LENGTH,
    WeakPasswordError,
    hash_password,
    validate_password_strength,
    verify_password,
)
from scripts import create_organizer

# Hasło spełniające politykę: dość długie i bez oczywistych fragmentów.
# `gitleaks:allow` jest tu konieczne - skaner sekretów widzi długi ciąg
# o wysokiej entropii przypisany do nazwy z "PASSWORD" i zgłasza go jako
# wyciek. Nie da się go odróżnić od prawdziwego sekretu inaczej niż jawnym
# wyjątkiem, a obniżanie entropii pod skaner dałoby hasło niereprezentatywne
# dla tego, co polityka ma przepuszczać.
GOOD_PASSWORD = "Zielony-Rower-Na-Moscie-77"  # gitleaks:allow


@pytest.fixture
def email_prefix() -> str:
    """Unikalny prefiks adresu + sprzątanie, wzorem testów zgłoszeń.

    Testy dzielą jedną bazę, więc stała nazwa konta zderzałaby się między
    przebiegami i zależała od kolejności.
    """
    prefix = f"org-{uuid4().hex[:10]}-"
    yield prefix

    async def cleanup() -> None:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM organizers WHERE email LIKE :p"), {"p": f"{prefix}%"}
            )
        await engine.dispose()

    asyncio.run(cleanup())


# --- polityka haseł ---


@pytest.mark.parametrize("password", ["", "krotkie", "x" * (PASSWORD_MIN_LENGTH - 1)])
def test_za_krotkie_haslo_jest_odrzucane(password: str) -> None:
    with pytest.raises(WeakPasswordError, match="co najmniej"):
        validate_password_strength(password)


@pytest.mark.parametrize(
    "password",
    [
        "hackathon2026alk",
        "SuperAdminSuperAdmin",
        "mojeHasloJestDlugie",
        "QwertyQwertyQwerty",
    ],
)
def test_oczywiste_haslo_jest_odrzucane_mimo_dlugosci(password: str) -> None:
    """Wszystkie te hasła spełniają limit długości - odpadają na treści.

    To jest sedno tej reguły: sama długość przepuszcza "hackathon2026alk",
    czyli pierwszą rzecz, jaką ktoś wpisze przy tym projekcie.
    """
    assert len(password) >= PASSWORD_MIN_LENGTH
    with pytest.raises(WeakPasswordError, match="oczywisty fragment"):
        validate_password_strength(password)


def test_poprawne_haslo_przechodzi() -> None:
    validate_password_strength(GOOD_PASSWORD)


# --- hashowanie ---


def test_hash_nie_zawiera_hasla() -> None:
    """Oczywiste, a jednak warte testu: to jedyna rzecz, której naprawdę
    nie wolno zapisać w bazie."""
    digest = hash_password(GOOD_PASSWORD)

    assert GOOD_PASSWORD not in digest
    assert digest.startswith("$argon2id$")


def test_weryfikacja_rozpoznaje_poprawne_i_bledne_haslo() -> None:
    digest = hash_password(GOOD_PASSWORD)

    assert verify_password(GOOD_PASSWORD, digest) is True
    assert verify_password(GOOD_PASSWORD + "x", digest) is False
    assert verify_password("", digest) is False


def test_to_samo_haslo_daje_rozne_hashe() -> None:
    """Sól jest losowa, więc dwa konta z tym samym hasłem mają różne hashe.

    Bez tego wyciek bazy pokazywałby, którzy organizatorzy mają identyczne
    hasło, a jedno złamanie otwierałoby wszystkie takie konta naraz.
    """
    first = hash_password(GOOD_PASSWORD)
    second = hash_password(GOOD_PASSWORD)

    assert first != second
    assert verify_password(GOOD_PASSWORD, first)
    assert verify_password(GOOD_PASSWORD, second)


# --- ograniczenia po stronie bazy ---


def test_baza_odrzuca_adres_z_wielkimi_literami(email_prefix: str) -> None:
    """CHECK działa także wtedy, gdy ktoś ominie aplikację i wpisze INSERT ręcznie."""

    async def scenario() -> None:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO organizers (email, password_hash) VALUES (:e, :h)"),
                    {"e": f"{email_prefix}DUZE@alk.edu.pl", "h": hash_password(GOOD_PASSWORD)},
                )
        finally:
            await engine.dispose()

    with pytest.raises(IntegrityError, match="email_lowercase"):
        asyncio.run(scenario())


def test_baza_nie_pozwala_zalozyc_dwoch_kont_na_ten_sam_adres(email_prefix: str) -> None:
    address = f"{email_prefix}duplikat@alk.edu.pl"

    async def scenario() -> None:
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                for _ in range(2):
                    await conn.execute(
                        text("INSERT INTO organizers (email, password_hash) VALUES (:e, :h)"),
                        {"e": address, "h": hash_password(GOOD_PASSWORD)},
                    )
        finally:
            await engine.dispose()

    with pytest.raises(IntegrityError):
        asyncio.run(scenario())


# --- skrypt zakładający konto ---


def test_adres_organizatora_jest_normalizowany() -> None:
    assert OrganizerEmail(email="  Jan.Kowalski@ALK.edu.PL  ").email == "jan.kowalski@alk.edu.pl"


def test_skrypt_odrzuca_niepoprawny_adres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "to-nie-jest-adres")

    with pytest.raises(SystemExit):
        create_organizer._read_email()


def test_skrypt_odrzuca_slabe_haslo_przed_zapisem(monkeypatch: pytest.MonkeyPatch) -> None:
    """Polityka musi zadziałać PRZED dotknięciem bazy - inaczej powstałoby
    konto, które potem trzeba by kasować ręcznie."""
    monkeypatch.setattr(create_organizer, "getpass", lambda _: "krotkie")

    with pytest.raises(SystemExit):
        create_organizer._read_password()


def test_skrypt_wymaga_zgodnego_powtorzenia_hasla(monkeypatch: pytest.MonkeyPatch) -> None:
    """Literówka w niewidocznym haśle zablokowałaby konto bez śladu - w bazie
    jest tylko hash, więc nie da się później sprawdzić, co zostało wpisane."""
    podane = iter([GOOD_PASSWORD, GOOD_PASSWORD + "literowka"])
    monkeypatch.setattr(create_organizer, "getpass", lambda _: next(podane))

    with pytest.raises(SystemExit):
        create_organizer._read_password()


def test_skrypt_zaklada_konto_i_odmawia_duplikatu(email_prefix: str) -> None:
    """Pełna droga skryptu: zapis, a potem ta sama próba raz jeszcze.

    Wszystko w JEDNEJ pętli zdarzeń, bo silnik aplikacji trzyma pulę połączeń
    przypiętych do pętli, w której powstały (powód opisany w `conftest.py`).
    Dwa osobne `asyncio.run` wywróciłyby się na tym, a nie na testowanej
    logice - skrypt w prawdziwym użyciu i tak startuje raz na proces.
    """
    address = f"{email_prefix}nowy@alk.edu.pl"

    async def scenario() -> int:
        await create_organizer._create(address, hash_password(GOOD_PASSWORD))

        with pytest.raises(SystemExit):
            await create_organizer._create(address, hash_password(GOOD_PASSWORD))

        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT count(*) FROM organizers WHERE email = :e"), {"e": address}
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    assert asyncio.run(scenario()) == 1
