from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.errors import validation_exception_handler
from app.routers import health, matching, submissions
from app.settings import settings

app = FastAPI(title="hackathon-matching API")

app.include_router(health.router)
app.include_router(submissions.router)
app.include_router(matching.router)

# Domyślne komunikaty walidacji pydantica są po angielsku, a front pokazuje je
# uczestnikowi wprost - stąd własny handler (patrz app/errors.py).
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Adresy, którym przeglądarka pozwoli odczytać odpowiedzi z tego API. Lista
# domyślna (dev + produkcyjny front z Vercela) i czytanie zmiennych
# CORS_ALLOWED_ORIGINS / CORS_ALLOWED_ORIGIN_REGEX są w app/settings.py - tam też
# konfiguracja wpuszczająca obce strony ("*", "null", wzorzec typu ".*")
# zatrzymuje start aplikacji.
#
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
    allow_origins=settings.cors_origins,
    # Podgląd z Vercela dostaje adres per gałąź, więc pojedyncze wpisy by nie
    # wystarczyły - ale wzorzec włącza się dopiero, gdy zespół świadomie go
    # ustawi (np. ^https://hackathon-matching-[a-z0-9-]+\.vercel\.app$).
    allow_origin_regex=settings.cors_allowed_origin_regex,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "hackathon-matching API"}
