from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db import get_readiness_engine
from app.services import health as service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def liveness() -> dict[str, str]:
    """Czy proces backendu żyje i odpowiada. Celowo NIE pyta bazy.

    To pytanie "czy trzeba mnie zrestartować?" - a restart backendu nie
    naprawi niedziałającej bazy. Czy backend może obsługiwać ruch, mówi
    `/health/ready`; tam powinny patrzeć docker compose i Railway.
    """
    return {"status": "ok"}


@router.get("/ready")
async def readiness(engine: AsyncEngine = Depends(get_readiness_engine)) -> JSONResponse:
    """Czy backend może obsługiwać żądania, czyli czy odpowiada mu baza (#91).

    Wcześniej jedyne sprawdzenie zdrowia odpowiadało "ok" nawet przy martwej
    bazie, więc każdy wskaźnik świecił na zielono, a lista zgłoszeń zwracała
    500. 503 ("usługa chwilowo niedostępna") to standardowy sygnał, na który
    reagują narzędzia do wdrożeń i monitoringu.

    Odpowiedź nie mówi, CO jest nie tak z bazą - to publiczny adres, a
    szczegóły (host, komunikat sterownika) lądują w logu serwera.
    """
    if await service.database_ready(engine):
        return JSONResponse({"status": "ok", "database": "ok"})
    return JSONResponse(
        {"status": "unavailable", "database": "unavailable"},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
