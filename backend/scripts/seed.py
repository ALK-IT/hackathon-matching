"""Wypełnia lokalną bazę zmyślonymi zgłoszeniami (#96).

Uruchomienie, z katalogu `backend/`:

    python -m scripts.seed              # dokłada 25 zgłoszeń
    python -m scripts.seed --count 30   # inna liczba
    python -m scripts.seed --clear      # najpierw kasuje POPRZEDNIE dane seeda

Po co: bez danych `POST /api/match` odpowiada 409 "brak zgłoszeń", a ręczne
wklepywanie dwudziestu curli tylko po to, żeby zobaczyć działające matchowanie,
jest stratą czasu. Przydaje się też pod dashboard rozkładu zgłoszeń (#80).

Dane są **deterministyczne**: ustawione ziarno sprawia, że każde uruchomienie
daje ten sam zestaw. Dzięki temu da się porównywać wyniki algorytmu między
przebiegami i mieć pewność, że różnica bierze się ze zmiany w kodzie, a nie
z innych danych wejściowych.
"""

import argparse
import asyncio
import sys

from faker import Faker
from sqlalchemy import delete, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.db import DATABASE_URL, SessionLocal, engine
from app.enums import ExperienceLevel, PreferredRole
from app.models import Submission, Team
from app.schemas import SubmissionCreate

DEFAULT_COUNT = 25

# Domena rekordów seeda - znacznik, po którym `--clear` je rozpoznaje.
# Jedno źródło prawdy dla generowania i sprzątania: gdyby te dwa miejsca się
# rozjechały, `--clear` przestałby cokolwiek kasować, a kolejne uruchomienie
# wywracało się na duplikatach.
#
# Cała domena, a nie prefiks adresu, bo prefiks bywa fragmentem prawdziwego
# adresu ("seed-fund@alk.edu.pl") i taki rekord zostałby skasowany razem
# z danymi testowymi. Domeny nie da się pomylić o tyle, że `example.com`
# jest zarezerwowane normą (RFC 2606): nikt nie może jej zarejestrować i nie
# dochodzi tam poczta, więc uczestnik nie ma jak się nią zgłosić - nie
# dostałby żadnej wiadomości o przydziale do zespołu.
#
# `.invalid` i `.test` byłyby jeszcze dosadniejsze, ale odrzuca je walidacja
# `EmailStr` ("special-use or reserved name"), a zależy nam, żeby dane seeda
# przechodziły dokładnie tę samą kontrolę co prawdziwy formularz.
SEED_EMAIL_DOMAIN = "seed.example.com"

# Ziarno dobrane raz i na stałe - patrz uwaga o determinizmie w nagłówku.
RANDOM_SEED = 2026

# Pula umiejętności zbliżona do tego, co realnie wpisują uczestnicy. Ma się
# przecinać między osobami, bo funkcja celu karze POWTÓRZENIA w zespole -
# gdyby każdy miał unikalny zestaw, ten składnik oceny byłby zawsze zerowy
# i seed nie pokazywałby, czy algorytm cokolwiek z nim robi.
SKILL_POOL = [
    "python",
    "javascript",
    "typescript",
    "react",
    "fastapi",
    "sql",
    "docker",
    "figma",
    "ux",
    "machine learning",
    "pandas",
    "git",
    "node",
    "css",
    "testing",
    "kubernetes",
]

# Adresy hostów, na których wolno działać. Skrypt KASUJE dane, a `DATABASE_URL`
# na maszynie dewelopera bywa przestawiony na zdalną bazę - bez tej zapory
# jedno `--clear` przy złym ustawieniu czyści zgłoszenia z produkcji.
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "postgres", ""})


def _require_local_database() -> None:
    """Przerywa, gdy DATABASE_URL nie wskazuje bazy lokalnej."""
    host = make_url(DATABASE_URL).host or ""
    if host not in LOCAL_HOSTS:
        print(
            f"Odmawiam: DATABASE_URL wskazuje na '{host}', a to skrypt wyłącznie "
            f"dla bazy lokalnej. Dozwolone hosty: {', '.join(sorted(LOCAL_HOSTS - {''}))}.",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _build_submissions(count: int) -> list[SubmissionCreate]:
    """Buduje zgłoszenia przechodzące przez tę samą walidację co API.

    Przepuszczamy je przez `SubmissionCreate`, a nie wprost do modelu ORM,
    żeby seed nie mógł wstawić danych, których prawdziwy formularz by nie
    przyjął - inaczej testowalibyśmy algorytm na wejściu niemożliwym
    w produkcji.

    Adresy budujemy sami, zamiast brać z Fakera: muszą być unikalne
    i wyłącznie ASCII, a `example.com` jest zarezerwowane normą i nigdy nie
    trafi do prawdziwej skrzynki.
    """
    faker = Faker("pl_PL")
    Faker.seed(RANDOM_SEED)

    levels = list(ExperienceLevel)
    roles = list(PreferredRole)

    submissions = []
    for index in range(count):
        submissions.append(
            SubmissionCreate(
                full_name=faker.name(),
                email=f"seed-{index:03d}@{SEED_EMAIL_DOMAIN}",
                skills=faker.random_elements(
                    SKILL_POOL, length=faker.random_int(2, 5), unique=True
                ),
                # Cykle o różnych długościach niż liczba zgłoszeń, żeby poziomy
                # i role przeplatały się zamiast układać w powtarzalny wzór.
                experience_level=levels[index % len(levels)],
                preferred_role=roles[(index * 3) % len(roles)],
                # Co czwarty uczestnik z niepełną dostępnością - inaczej
                # kryterium dostępności nie miałoby na czym pracować.
                availability=index % 4 != 0,
            )
        )
    return submissions


async def _clear() -> None:
    """Kasuje WYŁĄCZNIE rekordy seeda, rozpoznane po prefiksie adresu.

    Wcześniej było tu `delete(Submission)` i `delete(Team)` bez żadnego
    filtra, czyli czyszczenie całych tabel. Na współdzielonej lokalnej bazie
    z trwałym wolumenem (patrz `docker-compose.yml`) oznaczało to, że jedno
    `--clear` kasowało prawdziwe zgłoszenia wpisane ręcznie do testów -
    po cichu i bez możliwości odtworzenia.

    Filtrowanie po prefiksie jest zresztą wzorcem, który reszta repozytorium
    stosuje konsekwentnie: `_delete_by_prefix` w `test_match_hardening.py`
    i fixture'y sprzątające w testach zgłoszeń robią dokładnie to samo.

    Kolejność kroków wynika z powiązań:

    1. odpięcie od zespołów, bo `Submission.team_id` wskazuje na `teams`,
       a obiekty wczytane wcześniej trzymałyby w pamięci nieaktualną wartość;
    2. skasowanie zgłoszeń seeda;
    3. sprzątnięcie TYCH zespołów seeda, w których po skasowaniu nikt nie
       został. Zespół mieszany zostaje, bo wciąż ma prawdziwy skład; zespoły
       bez rekordów seeda nie są ruszane w ogóle - także puste, bo mogły
       powstać nie przez ten skrypt i mogą być komuś potrzebne.
    """
    pattern = f"%@{SEED_EMAIL_DOMAIN}"

    async with SessionLocal() as session:
        # Zespoły, w których siedzą rekordy seeda - ustalane ZANIM je odepniemy,
        # bo po odpięciu nie dałoby się już powiedzieć, gdzie były.
        zespoly_seeda = (
            (
                await session.execute(
                    select(Submission.team_id)
                    .where(Submission.email.like(pattern), Submission.team_id.is_not(None))
                    .distinct()
                )
            )
            .scalars()
            .all()
        )

        await session.execute(
            update(Submission).where(Submission.email.like(pattern)).values(team_id=None)
        )
        await session.execute(delete(Submission).where(Submission.email.like(pattern)))

        if zespoly_seeda:
            # Tylko te zespoły seeda, w których po skasowaniu nikt nie został.
            # Zespół mieszany (seed + prawdziwy uczestnik) zostaje, bo nadal ma
            # skład. Zespoły bez rekordów seeda nie są w ogóle rozpatrywane -
            # także puste, bo mogą być komuś potrzebne i nie nasza to sprawa.
            nadal_zajete = select(Submission.team_id).where(Submission.team_id.is_not(None))
            await session.execute(
                delete(Team).where(Team.id.in_(zespoly_seeda), Team.id.not_in(nadal_zajete))
            )

        await session.commit()


async def _insert(payloads: list[SubmissionCreate]) -> None:
    """Zapisuje komplet w jednej transakcji.

    Jedna transakcja, a nie zapis po jednym: seed ma albo wejść w całości,
    albo nie zostawić nic. Połowicznie wypełniona baza jest gorsza od pustej,
    bo wygląda na poprawną.
    """
    async with SessionLocal() as session:
        session.add_all(
            Submission(
                full_name=payload.full_name,
                email=payload.email,
                skills=payload.skills,
                experience_level=payload.experience_level,
                preferred_role=payload.preferred_role,
                availability=payload.availability,
            )
            for payload in payloads
        )
        await session.commit()


async def _run(count: int, clear: bool) -> None:
    """Cała praca w JEDNEJ pętli zdarzeń.

    To nie jest kosmetyka. Silnik aplikacji trzyma pulę połączeń przypiętych
    do pętli, w której powstały (powód opisany w `tests/conftest.py`). Osobne
    `asyncio.run` dla kasowania i dla zapisu oddawało połączenie do puli,
    a drugie wywołanie dostawało je z pętli już zamkniętej i kończyło się
    `RuntimeError: ... attached to a different loop` - po skasowaniu danych,
    a przed ich wstawieniem. Czyli w najgorszym możliwym momencie.
    """
    try:
        if clear:
            await _clear()
            print("Skasowano poprzednie dane seeda.")

        try:
            await _insert(_build_submissions(count))
        except IntegrityError:
            print(
                "Takie zgłoszenia już są w bazie - adresy seeda są stałe, więc dwa "
                "przebiegi się zderzają. Uruchom ponownie z --clear.",
                file=sys.stderr,
            )
            raise SystemExit(1) from None

        print(f"Dodano {count} zgłoszeń. Teraz POST /api/match ma co dzielić.")
    finally:
        # Bez tego pula zostaje z otwartymi połączeniami w chwili zamykania
        # pętli i interpreter kończy pracę ostrzeżeniami.
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Wypełnia lokalną bazę zmyślonymi zgłoszeniami.")
    parser.add_argument(
        "--count", type=int, default=DEFAULT_COUNT, help=f"ile zgłoszeń (domyślnie {DEFAULT_COUNT})"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="skasuj poprzednie dane seeda przed zapisem (nie rusza pozostałych rekordów)",
    )
    args = parser.parse_args()

    if args.count < 1:
        print("Liczba zgłoszeń musi być dodatnia.", file=sys.stderr)
        raise SystemExit(1)

    _require_local_database()

    asyncio.run(_run(args.count, args.clear))


if __name__ == "__main__":
    main()
