from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas import SubmissionCreate, SubmissionOut
from app.services import submissions as service

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
async def create_submission(
    payload: SubmissionCreate,
    session: AsyncSession = Depends(get_session),
) -> SubmissionOut:
    """Przyjmuje zgłoszenie uczestnika.

    Router nie dotyka bazy - jego zadaniem jest wyłącznie przełożenie
    wyjątku z warstwy serwisu na odpowiedni kod HTTP. Bez tego duplikat
    e-maila wyleciałby jako 500, czyli "coś się zepsuło po naszej stronie",
    zamiast czytelnej informacji, że adres jest już zajęty.
    """
    try:
        submission = await service.submit(session, payload)
    except service.DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Zgłoszenie z tym adresem e-mail już istnieje.",
        ) from None
    return SubmissionOut.model_validate(submission)


@router.get("", response_model=list[SubmissionOut])
async def list_submissions(
    session: AsyncSession = Depends(get_session),
) -> list[SubmissionOut]:
    """Zwraca wszystkie zgłoszenia do wyświetlenia na froncie.

    Brak zgłoszeń to poprawny stan (pusta lista), a nie błąd - stąd zwykłe
    200, bez dodatkowej obsługi wyjątków.
    """
    submissions = await service.get_all(session)
    return [SubmissionOut.model_validate(submission) for submission in submissions]
