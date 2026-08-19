from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    skills: str = Field(max_length=1000)


class SubmissionOut(BaseModel):
    """Zgłoszenie zwracane przez API, razem z polami nadanymi przez bazę."""

    # from_attributes pozwala zbudować ten model wprost z obiektu ORM,
    # bez ręcznego przepisywania pól.
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    skills: str
    created_at: datetime
