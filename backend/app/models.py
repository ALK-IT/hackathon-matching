from datetime import datetime
from enum import StrEnum

from sqlalchemy import ARRAY, Boolean, CheckConstraint, DateTime, Enum, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.enums import ExperienceLevel, PreferredRole


def _enum_column(enum_class: type[StrEnum], name: str) -> Enum:
    """Buduje kolumnę na enum Pythona zapisywaną w bazie jako tekst.

    `native_enum=False` świadomie rezygnuje z typu ENUM Postgresa. Natywny typ
    wygląda ładniej w schemacie, ale dołożenie do niego jednej wartości wymaga
    `ALTER TYPE` poza transakcją - a lista ról będzie rosnąć. Wersja tekstowa
    z ograniczeniem CHECK daje tę samą gwarancję na poziomie bazy, a jej zmiana
    to zwykłe przepięcie ograniczenia w migracji.

    `values_callable` zapisuje *wartości* enuma ("beginner"), a nie ich nazwy
    ("BEGINNER") - domyślnie SQLAlchemy trzyma w bazie nazwy, co rozjechałoby
    się z tym, co przyjmuje i zwraca API.

    Samo ograniczenie CHECK powstaje niżej, w `__table_args__`, a nie tutaj
    przez `create_constraint=True`. Ograniczenie zrobione przez `Enum` nie
    trafia do `Base.metadata` w postaci, którą widzi `alembic revision
    --autogenerate` - kolejna wygenerowana migracja próbowałaby je skasować
    jako "nadmiarowe w bazie". Zadeklarowane wprost jest widoczne dla obu stron.
    """
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=False,
        values_callable=lambda enum: [member.value for member in enum],
    )


def _allowed_values(column: str, enum_class: type[StrEnum]) -> str:
    values = ", ".join(f"'{member.value}'" for member in enum_class)
    return f"{column} IN ({values})"


class Submission(Base):
    """Pojedyncze zgłoszenie uczestnika na hackaton."""

    __tablename__ = "submissions"

    # Zbioru dopuszczalnych wartości pilnuje także baza, nie tylko pydantic.
    # Walidacja w API chroni przed błędem klienta, ograniczenie CHECK - również
    # przed błędem naszego kodu i ręcznym UPDATE-em (patrz SECURITY.md).
    # Nazwy muszą się zgadzać z tymi w migracji, inaczej autogenerate zobaczy
    # różnicę tam, gdzie jej nie ma.
    __table_args__ = (
        CheckConstraint(
            _allowed_values("experience_level", ExperienceLevel), name="experience_level"
        ),
        CheckConstraint(_allowed_values("preferred_role", PreferredRole), name="preferred_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True)

    # Lista, nie tekst po przecinkach: dopasowanie porównuje umiejętności
    # element po elemencie ("ilu ludzi w zespole zna Pythona"), a na stringu
    # znaczyłoby to LIKE po fragmencie - wolno i z pułapkami ("java" trafia
    # w "javascript"). Tablica Postgresa wystarcza i nie wymaga osobnej tabeli
    # ani JOIN-a; własna tabela `skills` ze słownikiem umiejętności ma sens
    # dopiero, gdy będziemy chcieli je normalizować albo podpowiadać w UI.
    skills: Mapped[list[str]] = mapped_column(ARRAY(String))

    # Kolumny profilu dopuszczają NULL, bo zgłoszenia zapisane przed tą zmianą
    # nie miały skąd wziąć tych danych. NULL znaczy tu "nie podano" i tak ma go
    # traktować algorytm dopasowania. Nowe zgłoszenia zawsze je mają - pilnuje
    # tego `SubmissionCreate`, gdzie oba pola są wymagane.
    experience_level: Mapped[ExperienceLevel | None] = mapped_column(
        _enum_column(ExperienceLevel, "experience_level"), nullable=True
    )
    preferred_role: Mapped[PreferredRole | None] = mapped_column(
        _enum_column(PreferredRole, "preferred_role"), nullable=True
    )

    # Czy uczestnik jest dostępny przez cały czas trwania hackatonu. Bool, bo
    # pytanie jest zamknięte - a nierówna dostępność to problem dla zespołu,
    # więc algorytm musi umieć takie osoby zgrupować. Domyślne `true` pozwoliło
    # wypełnić tę kolumnę w istniejących rekordach bez zgadywania czegokolwiek
    # innego niż najczęstszy przypadek.
    availability: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
