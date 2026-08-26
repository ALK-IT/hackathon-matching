from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.enums import MatchingAlgorithm
from app.schemas import TeamOut
from app.services import matching as service

router = APIRouter(prefix="/api/match", tags=["matching"])

# Górny limit rozmiaru zespołu. Nie wynika z algorytmu (ten poradzi sobie
# z każdą liczbą), tylko z tego, że wartość przychodzi z zewnątrz i nie ma
# powodu przyjmować liczb bez związku z hackatonem (patrz SECURITY.md).
# Dolna granica to 1, czyli tyle, ile dopuszcza `team_sizes` - API nie
# zaostrza kontraktu algorytmu, tylko go nie łamie.
MIN_TEAM_SIZE = 1
MAX_TEAM_SIZE = 20
DEFAULT_TEAM_SIZE = 4


@router.post("", response_model=list[TeamOut], status_code=status.HTTP_201_CREATED)
async def run_matching(
    team_size: int = Query(
        DEFAULT_TEAM_SIZE,
        ge=MIN_TEAM_SIZE,
        le=MAX_TEAM_SIZE,
        description="Górny limit liczby osób w zespole (nie rozmiar docelowy).",
    ),
    algorithm: MatchingAlgorithm = Query(
        MatchingAlgorithm.BALANCED,
        description="Wariant algorytmu; 'random' służy do porównania z 'balanced'.",
    ),
    session: AsyncSession = Depends(get_session),
) -> list[TeamOut]:
    """Układa zgłoszenia w zespoły i zwraca powstały podział.

    POST, mimo że nie przyjmuje ciała żądania: wywołanie **zmienia stan** -
    kasuje poprzedni podział i zapisuje nowy. GET musi być bezpieczny do
    powtórzenia (przeglądarki i pośredniki potrafią go ponowić same), więc
    ukrycie za nim takiej operacji byłoby proszeniem się o kłopoty.

    201, bo w bazie powstają nowe zespoły; ich pełną treść zwracamy od razu,
    żeby front nie musiał dopytywać osobnym żądaniem o to, co właśnie zlecił.

    Router nie dotyka bazy ani algorytmu - tłumaczy tylko wyjątek z warstwy
    serwisu na kod HTTP. Pusta baza to 409, a nie 500: żądanie jest poprawne,
    zawodzi stan aplikacji, i klient wie, co zrobić (dodać zgłoszenia).

    Parametry poza dopuszczalnym zakresem odsiewa FastAPI (422) razem
    z resztą walidacji - nie sprawdzamy ich tu drugi raz.
    """
    try:
        teams = await service.run_matching(session, team_size=team_size, algorithm=algorithm)
    except service.NoSubmissionsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Brak zgłoszeń do zmatchowania - najpierw dodaj uczestników.",
        ) from None
    return [TeamOut.model_validate(team) for team in teams]
