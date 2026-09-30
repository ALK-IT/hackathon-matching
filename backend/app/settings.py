"""Konfiguracja backendu w jednym miejscu (#95).

Wszystko, co różni się między laptopem, CI i serwerem, czyta ten moduł - reszta
kodu pyta `settings`, a nie `os.environ`. Dzięki temu błędna konfiguracja
wychodzi przy STARCIE, z komunikatem mówiącym, co poprawić, a nie przy pierwszym
żądaniu użytkownika jako błąd 500. Pełna lista ustawień jest też w
`backend/.env.example`.

Źródła, od najważniejszego: zmienne środowiskowe (panel Railway, docker compose,
CI), potem plik `.env` w katalogu, z którego uruchamiamy backend (lokalnie
`backend/`), na końcu wartości domyślne poniżej.
"""

import os
import re
from collections.abc import Mapping

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Adres bazy z docker-compose.yml. Lokalnie wolno go podstawić, bo tam taka baza
# faktycznie stoi obok - na serwerze pod "localhost" nie ma nic.
LOCAL_DATABASE_URL = "postgresql+asyncpg://hackathon:hackathon@localhost:5432/hackathon_matching"

# Zmienne, które Railway ustawia każdemu wdrożeniu sam (docs.railway.com,
# "Railway-provided variables"). Sprawdzamy kilka naraz, żeby wykrycie nie
# zależało od jednej nazwy, gdyby Railway ją kiedyś zmienił.
#
# Świadome ograniczenie (decyzja w #95): ochrona przed brakiem DATABASE_URL
# działa wyłącznie na Railway. Po przeprowadzce na inny hosting trzeba dopisać
# tu jego zmienne - inaczej backend znów podstawi localhost bez słowa.
RAILWAY_MARKERS = (
    "RAILWAY_ENVIRONMENT_ID",
    "RAILWAY_PROJECT_ID",
    "RAILWAY_SERVICE_ID",
    "RAILWAY_DEPLOYMENT_ID",
)

# Domyślne adresy, którym przeglądarka pozwoli odczytać odpowiedzi API: dev
# (Vite pod 5173, ten sam port co frontend z docker compose) i produkcyjny
# front z Vercela.
DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://hackathon-matching-chi.vercel.app",
)


# Adresy stron, których nie kontrolujemy. Wzorzec z CORS_ALLOWED_ORIGIN_REGEX,
# który do nich pasuje, wpuszcza obce strony - to ta sama dziura co "*", tylko
# zapisana inaczej (np. ".*" albo każda aplikacja na vercel.app). Ostatnia
# pozycja to Origin, który przeglądarka wysyła z ramek typu sandbox.
FOREIGN_ORIGINS = (
    "https://obca-strona.example",
    "http://obca-strona.example",
    "https://obca-strona.vercel.app",
    "null",
)


def running_on_railway(environ: Mapping[str, str] = os.environ) -> bool:
    return any(environ.get(name) for name in RAILWAY_MARKERS)


def allowed_origins(raw: str) -> list[str]:
    """Zamienia listę adresów po przecinku na listę dla CORS.

    Pusta wartość oznacza "zostań przy domyślnych", a nie "wpuść wszystkich":
    pomyłka w konfiguracji ma zamykać API, nie otwierać je na oścież.

    Końcowy ukośnik obcinamy, bo nagłówek `Origin` nigdy go nie ma -
    `https://front.example/` nie dopasowałoby się do niczego i wyglądało na
    awarię CORS-a, a nie na literówkę.

    Gwiazdka jest odrzucana (#60): API zwraca dane osobowe uczestników bez
    autoryzacji, więc "*" pozwoliłoby dowolnej stronie zaciągnąć listę
    zgłoszeń z przeglądarki odwiedzającego. "null" z tego samego powodu -
    taki Origin może wysłać każda strona, osadzając się w ramce sandbox.
    """
    origins = [origin.strip().rstrip("/") for origin in raw.split(",")]
    origins = [origin for origin in origins if origin]
    if "*" in origins or "null" in origins:
        raise ValueError(
            "CORS_ALLOWED_ORIGINS nie może zawierać '*' ani 'null' - API zwraca dane "
            "osobowe bez autoryzacji (#60). Podaj adresy frontendu po przecinku."
        )
    return origins or list(DEFAULT_ALLOWED_ORIGINS)


def check_origin_regex(pattern: str) -> None:
    """Rzuca ValueError, gdy wzorzec jest błędny albo wpuszcza obce strony.

    Błędny wzorzec trzeba złapać tutaj: Starlette kompiluje go dopiero przy
    pierwszym żądaniu, więc backend wstałby "zdrowy" i na każde żądanie
    odpowiadał 500. Komunikaty nie powtarzają wzorca - wystarczy nazwa zmiennej.
    """
    try:
        compiled = re.compile(pattern)
    except re.error as error:
        raise ValueError(
            "CORS_ALLOWED_ORIGIN_REGEX nie jest poprawnym wyrażeniem regularnym."
        ) from error
    # fullmatch, bo tak samo dopasowuje Starlette.
    if any(compiled.fullmatch(origin) for origin in FOREIGN_ORIGINS):
        raise ValueError(
            "CORS_ALLOWED_ORIGIN_REGEX wpuszcza obce strony - działa jak '*', zabronione "
            "w #60. Zawęź wzorzec do adresów zespołu, np. z nazwą projektu na Vercelu."
        )


class Settings(BaseSettings):
    # env_ignore_empty: pusta zmienna ("DATABASE_URL=" w panelu albo w .env) to
    # w praktyce "nie ustawiono". Bez tego pusta zmienna środowiskowa zasłaniała
    # wartość z .env, a pusty limit dawał niezrozumiały błąd parsowania liczby.
    #
    # hide_input_in_errors: komunikat błędu konfiguracji ląduje w logach serwera,
    # a pydantic domyślnie dokleja do niego surowe wartości - w tym DATABASE_URL
    # z hasłem do bazy. Nazwa pola i opis błędu wystarczą, żeby wiedzieć, co
    # poprawić.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    # O tym, co przy braku adresu, decyduje `_resolve_database_url`.
    # repr=False: adres zawiera hasło, a obiekt ustawień może trafić do logu
    # albo raportu błędu przez zwykłe wypisanie.
    database_url: str | None = Field(default=None, repr=False)

    # Lista po przecinku jako zwykły tekst, a nie list[str]: pydantic-settings
    # czytałby listę jako JSON, a na Railway ta zmienna jest ustawiana jako
    # "adres,adres". Gotową listę daje `cors_origins`.
    cors_allowed_origins: str = ""

    # Wzorzec dodatkowych adresów, np. podglądów z Vercela, które dostają adres
    # per gałąź. Włącza się dopiero, gdy zespół świadomie go ustawi.
    cors_allowed_origin_regex: str | None = None

    # Limity rozmiaru zespołu w POST /api/match. Nie wynikają z algorytmu (ten
    # poradzi sobie z każdą liczbą), tylko z tego, że wartość przychodzi
    # z zewnątrz (SECURITY.md). Dolna granica 1 to tyle, ile dopuszcza
    # `team_sizes`. Sufit 50: zespół hackatonowy większy niż kilkanaście osób
    # nie ma sensu, a sufit łapie literówkę typu 200.
    min_team_size: int = Field(default=1, ge=1, le=50)
    max_team_size: int = Field(default=20, ge=1, le=50)

    # Limit wszystkich zgłoszeń w bazie (#57). 3000 wyprowadzone z pomiarów:
    # największe realne hackathony to 1-2 tys. osób, a przy 3 tys. rekordów
    # niepaginowany GET /api/submissions zwraca ~0,6-0,7 MB JSON-u. Limit ma
    # zatrzymać MASOWE fałszywe zgłoszenia, nie 3001. uczestnika.
    #
    # Sufit 10 000 to granica bezpieczeństwa: powyżej odpowiedź listy bez
    # paginacji (#55) robi się ciężka - wyżej można iść dopiero po paginacji.
    max_total_submissions: int = Field(default=3000, ge=1, le=10_000)

    # Limit osób w jednym matchowaniu (#57). Nie chroni CPU - tym zajmuje się
    # budżet pracy w `_swap_repair` (balanced.py), przy 2000 osób przebieg
    # trwa ~1,7 s. Chroni rozmiar odpowiedzi: JSON z pełnymi składami to przy
    # 2000 osób ~0,5 MB. Sufit 5000 (~1,25 MB) z tego samego powodu.
    max_matched_participants: int = Field(default=2000, ge=1, le=5_000)

    @field_validator("database_url", "cors_allowed_origin_regex", mode="before")
    @classmethod
    def _trim(cls, value: object) -> object:
        # Spacja doklejona przy wklejaniu do panelu przeszłaby start i dała
        # bazę o nazwie "app " - czyli 500 przy każdym żądaniu, objaw z #95.
        # Same spacje (pustą wartość odsiewa już env_ignore_empty) to brak.
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def _valid_origins(cls, value: str) -> str:
        allowed_origins(value)  # rzuca ValueError przy "*" i "null"
        return value

    @field_validator("cors_allowed_origin_regex")
    @classmethod
    def _valid_origin_regex(cls, value: str | None) -> str | None:
        if value is not None:
            check_origin_regex(value)
        return value

    @model_validator(mode="after")
    def _resolve_database_url(self) -> "Settings":
        if self.database_url is None:
            if running_on_railway():
                raise ValueError(
                    "Brak DATABASE_URL na Railway - backend nie może wystartować bez adresu "
                    "bazy. Ustaw DATABASE_URL w zmiennych serwisu (referencja do bazy "
                    "Postgres w projekcie)."
                )
            self.database_url = LOCAL_DATABASE_URL
        return self

    @model_validator(mode="after")
    def _team_size_range(self) -> "Settings":
        if self.min_team_size > self.max_team_size:
            raise ValueError(
                f"MIN_TEAM_SIZE ({self.min_team_size}) nie może być większe niż "
                f"MAX_TEAM_SIZE ({self.max_team_size})."
            )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return allowed_origins(self.cors_allowed_origins)


# Jedna instancja na proces, tworzona przy imporcie: błędna konfiguracja
# zatrzymuje start aplikacji (a także alembica i testów) od razu.
settings = Settings()
