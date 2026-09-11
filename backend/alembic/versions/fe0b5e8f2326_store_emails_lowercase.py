"""store emails lowercase

Revision ID: fe0b5e8f2326
Revises: 7356d2184cb5
Create Date: 2026-09-10 19:58:57.653204

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "fe0b5e8f2326"
down_revision: str | Sequence[str] | None = "7356d2184cb5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Kolejnosc wdrozenia: NAJPIERW kod z #59, POTEM ta migracja. Stary kod zapisuje
# adres z duzymi literami przed "@", CHECK go odrzuci, a stary serwis pokaze to
# jako "e-mail juz istnieje" - zgloszenie przepadnie z falszywym komunikatem.
# Odwrotna kolejnosc jest bezpieczna: duplikat powstaly w oknie miedzy
# wdrozeniami zlapie glosne przerwanie nizej.

# Nazwa musi sie zgadzac z `name=` w __table_args__ w app/models.py, inaczej
# `alembic revision --autogenerate` zobaczy roznice tam, gdzie jej nie ma.
EMAIL_LOWERCASE = "email_lowercase"

# Adresy, ktore po sprowadzeniu do malych liter zderzylyby sie ze soba.
# Grupujemy tym samym lower() Postgresa, ktorego uzywa UPDATE i CHECK nizej -
# gdyby sprawdzenie liczylo male litery inaczej niz zmiana, moglaby przejsc
# kontrole i mimo to wylozyc sie na ograniczeniu unikalnosci.
CASE_DUPLICATES = """
    SELECT lower(email) AS address,
           array_agg(id ORDER BY id) AS ids,
           array_agg(email ORDER BY id) AS variants
    FROM submissions
    GROUP BY lower(email)
    HAVING count(*) > 1
    ORDER BY lower(email)
"""


def _abort_on_case_duplicates() -> None:
    """Przerywa migracje, jesli zamiana na male litery zderzylaby rekordy.

    Nie rozstrzygamy za czlowieka, ktore zgloszenie zostaje (decyzja w #59):
    automatyczne kasowanie mogloby usunac to, na ktorym komus zalezy.
    Wyjatek wycofuje cala transakcje, wiec baza zostaje dokladnie w stanie
    sprzed migracji.
    """
    duplicates = op.get_bind().execute(sa.text(CASE_DUPLICATES)).all()
    if not duplicates:
        return

    # Komunikat bez polskich znakow: alembic wypisuje go w konsoli, a konsola
    # Windows (cp1250) zamienia je na krzaczki.
    lines = [
        f"  {row.address}: rekordy {list(row.ids)} -> {list(row.variants)}" for row in duplicates
    ]
    raise RuntimeError(
        "Migracja przerwana: adresy rozniace sie tylko wielkoscia liter:\n"
        + "\n".join(lines)
        + "\nZostaw po jednym rekordzie z kazdej grupy i uruchom 'alembic upgrade head' ponownie."
    )


def upgrade() -> None:
    """Zastosuj zmianę schematu."""
    # Blokada calej tabeli od pierwszej chwili (przy naszej skali to milisekundy).
    # Bez niej zgloszenie zapisane miedzy sprawdzeniem a UPDATE ominie czytelne
    # przerwanie, a UPDATE (blokady wierszy) z ALTER-em (blokada tabeli) potrafi
    # zakleszczyc sie z rownoleglym matchowaniem. ALTER i tak potrzebuje tej
    # blokady - bierzemy ja od razu, zamiast podnosic w polowie.
    op.execute("LOCK TABLE submissions IN ACCESS EXCLUSIVE MODE")

    # W trybie offline (`alembic upgrade --sql`) nie ma polaczenia z baza, wiec
    # nie ma czego sprawdzic. Wygenerowany skrypt przy duplikacie wylozy sie na
    # ograniczeniu unikalnosci - surowszym komunikatem, ale bez szkody dla danych.
    if not context.is_offline_mode():
        _abort_on_case_duplicates()

    # Kolejnosc ma znaczenie: Postgres przy dodawaniu CHECK sprawdza tez wiersze,
    # ktore juz sa w tabeli, wiec najpierw porzadkujemy dane, potem ograniczenie.
    op.execute("UPDATE submissions SET email = lower(email) WHERE email <> lower(email)")
    op.create_check_constraint(EMAIL_LOWERCASE, "submissions", "email = lower(email)")


def downgrade() -> None:
    """Wycofaj zmianę schematu."""
    # Zdejmujemy tylko ograniczenie. Pierwotnej wielkosci liter nie da sie
    # przywrocic - upgrade swiadomie ja wyrzucil, bo w adresie nic nie znaczy.
    op.drop_constraint(EMAIL_LOWERCASE, "submissions", type_="check")
