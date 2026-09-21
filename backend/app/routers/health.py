from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db import get_readiness_engine
from app.services import health as service
from app.services.health import Readiness

router = APIRouter(prefix="/health", tags=["health"])

# Odpowiedź mówi, CO jest nie tak (baza czy schemat), ale bez szczegółów - to
# publiczny adres. Host bazy, komunikat sterownika i numery wersji schematu
# lądują w logu serwera.
READINESS_RESPONSES: dict[Readiness, tuple[int, dict[str, str]]] = {
    Readiness.READY: (
        status.HTTP_200_OK,
        {"status": "ok", "database": "ok", "schema": "ok"},
    ),
    Readiness.DATABASE_UNAVAILABLE: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        {"status": "unavailable", "database": "unavailable", "schema": "unknown"},
    ),
    Readiness.SCHEMA_OUTDATED: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        {"status": "unavailable", "database": "ok", "schema": "outdated"},
    ),
}


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
    """Czy backend może obsługiwać żądania (#91): baza odpowiada I ma wykonane
    wszystkie migracje.

    Wcześniej jedyne sprawdzenie zdrowia odpowiadało "ok" nawet przy martwej
    bazie, więc każdy wskaźnik świecił na zielono, a lista zgłoszeń zwracała
    500. Samo połączenie też nie wystarcza: pusta baza (np. po przywróceniu
    hostingu) odpowiada, ale nie ma tabel. 503 ("usługa chwilowo niedostępna")
    to standardowy sygnał, na który reagują narzędzia do wdrożeń i monitoringu.
    """
    status_code, body = READINESS_RESPONSES[await service.check_readiness(engine)]
    return JSONResponse(body, status_code=status_code)
