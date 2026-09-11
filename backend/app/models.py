from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    #
    # To samo dotyczy e-maila: trzymamy go wyłącznie małymi literami (#59).
    # Sprowadza go do nich `SubmissionCreate`, a CHECK odrzuca każdy zapis,
    # który tę normalizację ominął. Razem z unikalnością wyklucza to adresy
    # różniące się tylko wielkością liter - dla ASCII, polskich liter i niemal
    # całego Unicode. Wyjątki to tureckie "İ" i grecka końcowa sigma, które
    # Python zmniejsza inaczej niż Postgres; świadomie akceptujemy ten margines.
    __table_args__ = (
        CheckConstraint(
            _allowed_values("experience_level", ExperienceLevel), name="experience_level"
        ),
        CheckConstraint(_allowed_values("preferred_role", PreferredRole), name="preferred_role"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
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

    # Zespół, do którego dopasowanie przypisało to zgłoszenie. Kolumna po
    # stronie zgłoszenia, a nie tabela łącząca, bo dzięki temu ograniczenie
    # "jedno zgłoszenie = najwyżej jeden zespół" pilnuje sam schemat: kolumna
    # mieści jedną wartość i nie da się jej obejść ani błędem w kodzie, ani
    # ręcznym INSERT-em. Tabela many-to-many dopuszczałaby stan, którego i tak
    # musielibyśmy zabraniać osobnym ograniczeniem unikalności.
    #
    # NULL znaczy "jeszcze nie dopasowany" - tak wygląda każde zgłoszenie
    # przed pierwszym uruchomieniem matchowania.
    #
    # ondelete="SET NULL": skasowanie zespołu nie kasuje ludzi, tylko zdejmuje
    # im przypisanie. Zgłoszenie jest danymi od uczestnika, zespół - wynikiem
    # algorytmu, który przeliczamy do skutku; kasowanie pierwszego razem
    # z drugim byłoby utratą danych nie do odzyskania.
    #
    # index=True, bo po tej kolumnie chodzi każde wczytanie składów zespołów
    # (JOIN/`selectinload` po `team_id`), a Postgres nie zakłada indeksu na
    # kluczu obcym sam z siebie - inaczej niż na kluczu głównym.
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    team: Mapped["Team | None"] = relationship(back_populates="members")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Team(Base):
    """Zespół utworzony przez uruchomienie dopasowania.

    Model jest celowo pusty poza identyfikatorem i czasem powstania: cała
    treść zespołu to jego skład, a ten trzyma kolumna `Submission.team_id`.
    Nazwa czy opis zespołu nie należą do wyniku algorytmu - gdyby miały
    powstać, będzie to osobne zadanie i osobna kolumna.

    Każde uruchomienie matchowania buduje zespoły od zera (patrz
    `app/repositories/teams.py`), więc `created_at` mówi wprost, kiedy
    powstał aktualny podział.
    """

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Skład zespołu. Relacja jest wygodą warstwy serwisu i schematów - zapytania
    # nadal należą wyłącznie do repozytorium (patrz CLAUDE.md).
    #
    # Uwaga na asynchroniczność: domyślne leniwe ładowanie kolekcji dosypuje
    # SELECT dopiero przy odczycie atrybutu, a w kodzie async kończy się to
    # wyjątkiem `MissingGreenlet` zamiast danymi. Dlatego repozytorium wczytuje
    # zespoły jawnie przez `selectinload`, a świeżo utworzone mają skład
    # ustawiony wprost w Pythonie - żadna ścieżka nie liczy na leniwe doczytanie.
    #
    # `order_by`: bez tego kolejność członków zespołu w odpowiedzi API zależy
    # od tego, co akurat zwróci baza, i potrafi się zmieniać między żądaniami
    # przy tych samych danych.
    members: Mapped[list["Submission"]] = relationship(
        back_populates="team", order_by="Submission.id"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Organizer(Base):
    """Konto organizatora - jedyna tożsamość, jaką zna to API (SPEC-005).

    Uczestnicy kont nie mają i mieć nie będą: zgłoszenie wysyła się bez
    logowania, a `Submission` nie jest z tym modelem w żaden sposób powiązane.
    To celowe zawężenie zakresu z #68 - tu nie ma rejestracji uczestników,
    jest formularz.

    Kont nie da się założyć przez API. Nie ma na to endpointu i nie będzie
    w tym zakresie: jedyną drogą jest `scripts/create_organizer.py`, czyli
    ktoś z dostępem do serwera. Endpoint rejestracji organizatora byłby
    najkrótszą drogą do tego, żeby uczestnik hackathonu założył sobie konto
    administratora.
    """

    __tablename__ = "organizers"

    __table_args__ = (
        # Ten sam CHECK co przy zgłoszeniach (#59). Walidacja w Pythonie
        # sprowadza adres do małych liter, ale baza nie może na to liczyć:
        # skrypt zakładający konto i ewentualna ręczna poprawka w SQL omijają
        # warstwę aplikacji, a wtedy "Jan@alk.pl" i "jan@alk.pl" byłyby dwoma
        # różnymi kontami mimo ograniczenia unikalności.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Login organizatora. Adres, a nie dowolna nazwa użytkownika, bo przy
    # kilku osobach w zespole "kto to jest admin2" jest pytaniem bez odpowiedzi,
    # a e-mail wskazuje konkretnego człowieka.
    email: Mapped[str] = mapped_column(String(320), unique=True)

    # Wyłącznie hash, nigdy hasło. Długość z zapasem: argon2id produkuje dziś
    # ok. 100 znaków, ale zmiana parametrów albo algorytmu (pwdlib potrafi
    # przehashować przy logowaniu) potrafi ten wynik wydłużyć, a kolumna za
    # ciasna ucięłaby hash i zablokowała logowanie właścicielowi konta.
    password_hash: Mapped[str] = mapped_column(String(512))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
