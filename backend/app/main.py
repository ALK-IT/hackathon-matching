import os

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import validation_exception_handler
from app.routers import matching, submissions

app = FastAPI(title="hackathon-matching API")

app.include_router(submissions.router)
app.include_router(matching.router)

# Domyślne komunikaty walidacji pydantica są po angielsku, a front pokazuje je
# uczestnikowi wprost - stąd własny handler (patrz app/errors.py).
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Adresy, którym przeglądarka pozwoli odczytać odpowiedzi z tego API.
#
# Wartość domyślna obejmuje dev (Vite pod 5173, ten sam port co frontend
# z docker compose) i produkcyjny front z Vercela. Na Railway podmienia się
# ją zmienną CORS_ALLOWED_ORIGINS - lista po przecinku - żeby zmiana adresu
# frontendu nie wymagała wydania nowej wersji backendu.
DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://hackathon-matching-chi.vercel.app",
)


def allowed_origins(raw: str | None = None) -> list[str]:
    """Czyta listę dozwolonych originów ze zmiennej środowiskowej.

    Pusta albo niepodana zmienna oznacza "zostań przy domyślnych", a nie
    "wpuść wszystkich": pomyłka w konfiguracji ma zamykać API, nie otwierać
    je na oścież.

    Końcowy ukośnik obcinamy, bo nagłówek `Origin` nigdy go nie ma -
    `https://front.example/` wpisane w konfiguracji nie dopasowałoby się
    do niczego i wyglądałoby na awarię CORS-a, a nie na literówkę.

    `raw` jest po to, żeby dało się to przetestować bez ruszania środowiska
    procesu.
    """
    value = raw if raw is not None else os.environ.get("CORS_ALLOWED_ORIGINS", "")
    origins = [origin.strip().rstrip("/") for origin in value.split(",")]
    return [origin for origin in origins if origin] or list(DEFAULT_ALLOWED_ORIGINS)


# Gwiazdka w allow_origins zniknęła świadomie (#60). API zwraca dane osobowe
# uczestników (imię, e-mail, umiejętności) bez autoryzacji, więc przy "*"
# dowolna strona w internecie mogła zaciągnąć całą listę zgłoszeń fetch-em
# z przeglądarki swojego odwiedzającego. To nie zastępuje autoryzacji (#55):
# CORS obowiązuje wyłącznie przeglądarki, curl czy skrypt nadal wejdą bez
# przeszkód. Podnosi natomiast koszt najprostszego wariantu ataku.
#
# Metody i nagłówki zawężone do tego, czego front faktycznie używa. Gdy
# dojdzie autoryzacja (#68), do allow_headers trzeba dopisać "Authorization",
# a przy edycji/wycofaniu zgłoszenia (#71) - PATCH i DELETE.
#
# allow_credentials zostaje wyłączone (domyślnie): ciasteczek sesyjnych nie
# używamy, a włączenie ich razem z szeroką listą originów to klasyczny sposób
# na przypadkowe udostępnienie sesji obcej stronie.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    # Podgląd z Vercela dostaje adres per gałąź, więc pojedyncze wpisy by nie
    # wystarczyły - ale wzorzec włącza się dopiero, gdy zespół świadomie go
    # ustawi (np. ^https://hackathon-matching-[a-z0-9-]+\.vercel\.app$).
    allow_origin_regex=os.environ.get("CORS_ALLOWED_ORIGIN_REGEX") or None,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "hackathon-matching API"}


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello World z backendu hackathon-matching!"}


@app.get("/api/db-check")
async def db_check(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    """Przykład komunikacji z Postgresem - sprawdza czy polaczenie dziala."""
    result = await session.execute(text("SELECT 1"))
    result.scalar_one()
    return {"status": "ok", "database": "connected"}
