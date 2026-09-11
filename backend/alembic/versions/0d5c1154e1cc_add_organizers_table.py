"""add organizers table

Revision ID: 0d5c1154e1cc
Revises: fe0b5e8f2326
Create Date: 2026-09-11 16:13:16.954575

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0d5c1154e1cc"
down_revision: str | Sequence[str] | None = "fe0b5e8f2326"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Nowa, pusta tabela - nie ma danych do przeniesienia, wiec migracja nie
# potrzebuje oslon w rodzaju tych z fe0b5e8f2326 (tamta poprawiala istniejace
# adresy). Kolejnosc wdrozenia jest tu obojetna: kod bez tabeli po prostu nie
# ma jak sie zalogowac, a tabela bez kodu nikomu nie przeszkadza.

# Nazwa ograniczenia musi sie zgadzac z `name=` w __table_args__ w models.py -
# inaczej kolejne `alembic revision --autogenerate` zobaczy roznice tam, gdzie
# jej nie ma, i zaproponuje migracje kasujaca i zakladajaca to samo.


def upgrade() -> None:
    """Zakłada tabelę kont organizatorów (SPEC-005, #119)."""
    op.create_table(
        "organizers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("email = lower(email)", name="email_lowercase"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )


def downgrade() -> None:
    """Kasuje tabelę kont razem z kontami.

    Wycofanie tej migracji USUWA wszystkie konta organizatorów - nie da się ich
    odtworzyć, bo w bazie są tylko hashe, a nie hasła. Nie jest to jednak
    strata nieodwracalna w praktyce: konta zakłada się skryptem
    `scripts/create_organizer.py` i wystarczy zrobić to ponownie.
    """
    op.drop_table("organizers")
