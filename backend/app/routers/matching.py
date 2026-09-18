from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.enums import MatchingAlgorithm
from app.schemas import TeamOut
from app.services import matching as service
from app.settings import settings

router = APIRouter(prefix="/api/match", tags=["matching"])

# Zakres rozmiaru zespołu - wartości i ich uzasadnienie w app/settings.py.
MIN_TEAM_SIZE = settings.min_team_size
MAX_TEAM_SIZE = settings.max_team_size

# Domyślny rozmiar, gdy żądanie go nie poda. Przycięty do zakresu, bo zakres
# da się zmienić w konfiguracji - bez tego np. MAX_TEAM_SIZE=3 odrzucałoby
# żądanie BEZ parametru, którego użytkownik w ogóle nie podał.
DEFAULT_TEAM_SIZE = min(max(4, MIN_TEAM_SIZE), MAX_TEAM_SIZE)


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
    except service.MatchingInProgressError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Matchowanie już trwa - poczekaj na zakończenie poprzedniego przebiegu.",
        ) from None
    except service.TooManyParticipantsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Zbyt wiele zgłoszeń do zmatchowania - skontaktuj się z organizatorem.",
        ) from None
    return [TeamOut.model_validate(team) for team in teams]
