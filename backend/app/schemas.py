from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.enums import ExperienceLevel, PreferredRole

# Pojedyncza umiejętność. Limit długości jest tu, a nie na całej liście, bo
# ograniczenie "1000 znaków razem" da się obejść jedną gigantyczną pozycją.
Skill = Annotated[str, Field(min_length=1, max_length=50)]


class SubmissionCreate(BaseModel):
    """Dane przychodzące od uczestnika przy wysyłaniu zgłoszenia.

    Górne limity długości są celowe: bez nich można wysłać dowolnie duży
    tekst i zapchać bazę (patrz SECURITY.md - walidacja wszystkich wejść).
    """

    # Obcinanie białych znaków sprawia, że samo "   " nie przejdzie
    # przez min_length i skończy się błędem 422, a nie pustym imieniem w bazie.
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr = Field(max_length=320)

    # Lista, nie tekst po przecinkach - powód przy kolumnie `skills` w models.py.
    # Limit 20 pozycji: tyle wystarczy do dopasowania, a odcina wklejenie
    # całego CV jako tysiąca "umiejętności".
    skills: list[Skill] = Field(min_length=1, max_length=20)

    # Oba pola profilu są wymagane, mimo że kolumny w bazie dopuszczają NULL.
    # NULL jest zarezerwowany dla zgłoszeń sprzed rozszerzenia modelu; nowe
    # zgłoszenie bez tych danych byłoby dla algorytmu bezużyteczne.
    experience_level: ExperienceLevel
    preferred_role: PreferredRole

    # Domyślnie zakładamy pełną dostępność - to najczęstszy przypadek, a pole
    # pojawiło się później niż samo zgłoszenie, więc brak wartości nie powinien
    # odrzucać żądania.
    availability: bool = True

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, skills: list[str]) -> list[str]:
        """Sprowadza umiejętności do wspólnej postaci i usuwa powtórzenia.

        Dopasowanie porównuje umiejętności dosłownie, więc "React" i "react"
        muszą być tym samym wpisem - inaczej dwoje ludzi znających to samo
        wygląda w danych na dwie różne kompetencje. Powtórzenia w jednym
        zgłoszeniu zawyżałyby natomiast wagę takiej osoby.

        `dict.fromkeys` zachowuje kolejność wpisaną przez uczestnika - pierwsze
        pozycje zwykle są tymi, które uważa za najmocniejsze.
        """
        return list(dict.fromkeys(skill.lower() for skill in skills))

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, email: object) -> object:
        """Sprowadza cały adres do małych liter (#59).

        `EmailStr` sam zmniejsza tylko domenę (część po "@"), bo standard
        poczty formalnie pozwala rozróżniać wielkość liter przed "@". Żaden
        popularny dostawca z tego nie korzysta, a bez tej normalizacji
        "Jan@example.com" i "jan@example.com" przechodziły jako dwa zgłoszenia
        jednej osoby - i dwa miejsca w matchowaniu.

        `mode="before"`: zmniejszamy PRZED walidacją `EmailStr`, żeby limit
        długości i pozostałe reguły sprawdzały dokładnie to, co trafi do bazy.
        `lower()` potrafi wydłużyć adres ("İ" to po nim dwa znaki), a rekord
        zapisany ponad limitem nie przeszedłby walidacji przy odczycie
        (`SubmissionOut`) i wywracałby całą listę zgłoszeń.

        `lower()`, nie `casefold()`: casefold zamienia np. "ß" na "ss", czyli
        zmienia sam adres, a nie tylko wielkość liter.
        """
        return email.lower() if isinstance(email, str) else email


class SubmissionOut(BaseModel):
    """Zgłoszenie zwracane przez API, razem z polami nadanymi przez bazę."""

    # from_attributes pozwala zbudować ten model wprost z obiektu ORM,
    # bez ręcznego przepisywania pól.
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    skills: list[str]
    # Dopuszczają None wyłącznie dla zgłoszeń sprzed rozszerzenia modelu -
    # front musi się liczyć z pustą wartością w tych rekordach.
    experience_level: ExperienceLevel | None
    preferred_role: PreferredRole | None
    availability: bool
    created_at: datetime


class TeamOut(BaseModel):
    """Zespół zwracany przez API razem z pełnym składem.

    Skład jest zagnieżdżony, a nie podany jako lista identyfikatorów, bo
    jedyny sensowny widok wyniku matchowania to "kto z kim" - przy samych
    `id` front musiałby dociągać każde zgłoszenie osobno, żeby cokolwiek
    pokazać.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    members: list[SubmissionOut]
    created_at: datetime
