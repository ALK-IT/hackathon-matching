"""add team model

Revision ID: 7356d2184cb5
Revises: ea5f5df7cdb3
Create Date: 2026-08-26 02:22:26.838410

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7356d2184cb5"
down_revision: str | Sequence[str] | None = "ea5f5df7cdb3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Klucz obcy dostaje nazwe jawnie, mimo ze `alembic revision --autogenerate`
# zostawil tu None. Bez nazwy `downgrade` nie ma czego skasowac (op.drop_constraint
# potrzebuje nazwy), a nazwa nadana przez Postgresa nie jest czescia kontraktu -
# nie ma gwarancji, ze na innej bazie wyjdzie taka sama.
FK_SUBMISSIONS_TEAM = "fk_submissions_team_id_teams"
IX_SUBMISSIONS_TEAM = "ix_submissions_team_id"


def upgrade() -> None:
    """Zastosuj zmianę schematu."""
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Sklad zespolu trzyma kolumna po stronie zgloszenia, a nie tabela laczaca -
    # uzasadnienie przy `Submission.team_id` w app/models.py.
    #
    # NULL jest tu konieczny: w tabeli sa juz zgloszenia, a zadne z nich nie ma
    # jeszcze zespolu. NOT NULL wymagaloby wymyslenia im przypisania, ktorego
    # nikt nie policzyl.
    op.add_column("submissions", sa.Column("team_id", sa.Integer(), nullable=True))

    # Indeks na kluczu obcym zaklada sie recznie - Postgres robi to sam tylko
    # dla klucza glownego. Po tej kolumnie chodzi kazde wczytanie skladow.
    op.create_index(IX_SUBMISSIONS_TEAM, "submissions", ["team_id"], unique=False)

    # ON DELETE SET NULL: skasowanie zespolu zdejmuje ludziom przypisanie,
    # ale ich nie kasuje. Zgloszenie to dane od uczestnika, zespol - wynik
    # algorytmu, ktory przeliczamy do skutku.
    op.create_foreign_key(
        FK_SUBMISSIONS_TEAM,
        "submissions",
        "teams",
        ["team_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Wycofaj zmianę schematu."""
    op.drop_constraint(FK_SUBMISSIONS_TEAM, "submissions", type_="foreignkey")
    op.drop_index(IX_SUBMISSIONS_TEAM, table_name="submissions")
    op.drop_column("submissions", "team_id")
    op.drop_table("teams")
