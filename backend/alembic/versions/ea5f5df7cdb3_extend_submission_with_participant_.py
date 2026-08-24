"""extend submission with participant profile

Revision ID: ea5f5df7cdb3
Revises: 1552c6175bbe
Create Date: 2026-08-21 00:57:27.773619

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ea5f5df7cdb3"
down_revision: str | Sequence[str] | None = "1552c6175bbe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Migracja jest pisana recznie, nie przez `alembic revision --autogenerate`.
# Autogenerate widzi zmiane typu kolumny `skills`, ale nie wie, jak przeniesc
# dane - wygenerowalby ALTER bez klauzuli USING, a Postgres odmawia zamiany
# VARCHAR na VARCHAR[] bez jawnego przepisu na konwersje.

# Rozbicie dotychczasowego tekstu po przecinkach na tablice:
#   - regexp_replace zdejmuje spacje wokol przecinkow ("python, react"),
#   - btrim usuwa przecinki i spacje z brzegow (",python,"),
#   - lower ujednolica wielkosc liter - tak samo, jak robi to teraz walidacja
#     w SubmissionCreate, wiec stare i nowe rekordy sa porownywalne,
#   - pusty tekst daje pusta tablice, a nie tablice z jednym pustym wpisem.
SKILLS_TO_ARRAY = r"""
    CASE
        WHEN btrim(skills) = '' THEN ARRAY[]::varchar[]
        ELSE string_to_array(
            lower(btrim(regexp_replace(skills, '\s*,\s*', ',', 'g'), ' ,')),
            ','
        )
    END
"""

# Powrot do jednego tekstu: laczy elementy przecinkiem. Konwersja jest stratna
# tylko o tyle, ze umiejetnosc zawierajaca przecinek scalilaby sie z sasiednia -
# walidacja nie ma powodu takich wpisow przyjmowac, a downgrade to sciezka
# awaryjna, nie codzienna operacja.
SKILLS_TO_STRING = "array_to_string(skills, ',')"

EXPERIENCE_LEVELS = ("beginner", "intermediate", "advanced")
PREFERRED_ROLES = ("frontend", "backend", "fullstack", "design", "data", "pm", "other")


def _in_clause(column: str, values: Sequence[str]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    """Zastosuj zmianę schematu."""
    op.alter_column(
        "submissions",
        "skills",
        type_=sa.ARRAY(sa.String()),
        existing_type=sa.String(),
        existing_nullable=False,
        postgresql_using=SKILLS_TO_ARRAY,
    )

    # Kolumny profilu dopuszczaja NULL, bo zgloszenia zapisane wczesniej nie
    # maja tych danych, a wpisanie im domyslnego poziomu czy roli oznaczaloby
    # wymyslenie odpowiedzi za uczestnika. NULL czyta sie jako "nie podano".
    op.add_column("submissions", sa.Column("experience_level", sa.String(length=12), nullable=True))
    op.add_column("submissions", sa.Column("preferred_role", sa.String(length=9), nullable=True))

    # `availability` jest NOT NULL, bo tutaj domyslna odpowiedz jest uczciwa:
    # "dostepny caly czas" to zalozenie, na ktorym dzialal formularz do tej pory.
    op.add_column(
        "submissions",
        sa.Column("availability", sa.Boolean(), server_default=sa.true(), nullable=False),
    )

    # Zbior dopuszczalnych wartosci pilnuje takze baza, nie tylko pydantic -
    # walidacja w API chroni przed bledem klienta, ograniczenie CHECK takze
    # przed bledem naszego kodu i recznym UPDATE (patrz SECURITY.md).
    # Nazwy ograniczen musza zgadzac sie z `name=` w Enum w app/models.py,
    # inaczej `alembic revision --autogenerate` zobaczy roznice tam, gdzie jej nie ma.
    op.create_check_constraint(
        "experience_level", "submissions", _in_clause("experience_level", EXPERIENCE_LEVELS)
    )
    op.create_check_constraint(
        "preferred_role", "submissions", _in_clause("preferred_role", PREFERRED_ROLES)
    )


def downgrade() -> None:
    """Wycofaj zmianę schematu."""
    op.drop_constraint("preferred_role", "submissions", type_="check")
    op.drop_constraint("experience_level", "submissions", type_="check")
    op.drop_column("submissions", "availability")
    op.drop_column("submissions", "preferred_role")
    op.drop_column("submissions", "experience_level")

    op.alter_column(
        "submissions",
        "skills",
        type_=sa.String(),
        existing_type=sa.ARRAY(sa.String()),
        existing_nullable=False,
        postgresql_using=SKILLS_TO_STRING,
    )
