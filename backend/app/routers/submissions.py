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
