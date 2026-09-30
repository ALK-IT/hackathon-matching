"""Testy centralnej konfiguracji (#95).

Każdy test buduje `Settings(_env_file=None)`, żeby wynik nie zależał od pliku
backend/.env, który ktoś ma u siebie lokalnie - liczą się tylko zmienne
ustawione w teście.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.settings import (
    DEFAULT_ALLOWED_ORIGINS,
    LOCAL_DATABASE_URL,
    RAILWAY_MARKERS,
    Settings,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Każdy test zaczyna bez zmiennych, które zmieniają wynik - CI ustawia
    DATABASE_URL dla całego przebiegu, a ktoś może mieć u siebie CORS_*."""
    for name in (
        "DATABASE_URL",
        "CORS_ALLOWED_ORIGINS",
        "CORS_ALLOWED_ORIGIN_REGEX",
        "MIN_TEAM_SIZE",
        "MAX_TEAM_SIZE",
        "MAX_TOTAL_SUBMISSIONS",
        "MAX_MATCHED_PARTICIPANTS",
        *RAILWAY_MARKERS,
    ):
        monkeypatch.delenv(name, raising=False)


def on_railway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "test-environment")


# --- DATABASE_URL: głośno na Railway, cicho lokalnie (decyzja w #95) ---


def test_locally_missing_database_url_falls_back_to_compose_database() -> None:
    assert Settings(_env_file=None).database_url == LOCAL_DATABASE_URL


def test_on_railway_missing_database_url_stops_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sedno #95: na serwerze brak adresu bazy to błąd startu, a nie ciche
    podstawienie localhost, pod którym na serwerze nic nie ma."""
    on_railway(monkeypatch)

    with pytest.raises(ValidationError, match="Brak DATABASE_URL na Railway"):
        Settings(_env_file=None)


@pytest.mark.parametrize("marker", RAILWAY_MARKERS)
def test_every_railway_marker_is_enough(monkeypatch: pytest.MonkeyPatch, marker: str) -> None:
    """Wykrycie nie może zależeć od jednej zmiennej - wystarczy dowolna z nich."""
    monkeypatch.setenv(marker, "x")

    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(_env_file=None)


@pytest.mark.parametrize("value", ["", "   "])
def test_on_railway_blank_database_url_counts_as_missing(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Pusta zmienna w panelu to w praktyce brak zmiennej."""
    on_railway(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", value)

    with pytest.raises(ValidationError, match="Brak DATABASE_URL"):
        Settings(_env_file=None)


def test_database_url_is_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spacja doklejona przy wklejaniu do panelu dawała bazę o nazwie "app " -
    start przechodził, a każde żądanie kończyło się 500 (objaw z #95)."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.internal:5432/app ")

    assert Settings(_env_file=None).database_url == "postgresql://user:pass@db.internal:5432/app"


def test_blank_environment_variable_does_not_hide_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pusta zmienna środowiskowa to "nie ustawiono" - wartość z .env wygrywa,
    zamiast zniknąć i zostać po cichu zastąpiona domyślną."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql://user:pass@dev-db:5432/app\nMAX_TEAM_SIZE=8\n", encoding="utf-8"
    )
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("MAX_TEAM_SIZE", "")

    settings = Settings(_env_file=env_file)

    assert settings.database_url == "postgresql://user:pass@dev-db:5432/app"
    assert settings.max_team_size == 8


def test_on_railway_with_database_url_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    on_railway(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.internal:5432/app")

    assert Settings(_env_file=None).database_url == "postgresql://user:pass@db.internal:5432/app"


def test_startup_of_the_real_app_fails_on_railway_without_database_url(tmp_path: Path) -> None:
    """To samo na prawdziwym starcie: import aplikacji w osobnym procesie.

    Proces rusza w pustym katalogu, żeby nie wczytał backend/.env - inaczej
    test przeszedłby albo oblał zależnie od tego, co ktoś ma u siebie.
    """
    environment = {
        name: value
        for name, value in os.environ.items()
        if name != "DATABASE_URL" and name not in RAILWAY_MARKERS
    }
    environment |= {"PYTHONPATH": str(BACKEND_DIR), "RAILWAY_ENVIRONMENT_ID": "test-environment"}

    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,  # porażka procesu to tu oczekiwany wynik, sprawdzany niżej
    )

    assert result.returncode != 0
    assert "Brak DATABASE_URL na Railway" in result.stderr


# --- CORS ---


def test_empty_cors_means_default_origins() -> None:
    assert Settings(_env_file=None).cors_origins == list(DEFAULT_ALLOWED_ORIGINS)


def test_cors_list_is_split_and_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Na Railway lista jest ustawiana jako "adres,adres" - nie jako JSON."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.example/, https://b.example")

    assert Settings(_env_file=None).cors_origins == ["https://a.example", "https://b.example"]


@pytest.mark.parametrize("value", ["*", "https://a.example,*", " * ", "null"])
def test_cors_wildcard_stops_startup(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """#60 zabrało gwiazdkę z kodu - lista w konfiguracji nie może jej przywrócić.
    "null" wysyła każda strona osadzona w ramce sandbox, więc działa tak samo."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", value)

    with pytest.raises(ValidationError, match="nie może zawierać"):
        Settings(_env_file=None)


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_cors_regex_is_disabled(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGIN_REGEX", value)

    assert Settings(_env_file=None).cors_allowed_origin_regex is None


def test_invalid_cors_regex_stops_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Starlette kompiluje wzorzec dopiero przy pierwszym żądaniu - bez tej
    kontroli backend wstawał i na KAŻDE żądanie odpowiadał 500."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGIN_REGEX", "[sekretny-wzorzec")

    with pytest.raises(ValidationError, match="poprawnym wyrażeniem") as error:
        Settings(_env_file=None)

    assert "sekretny-wzorzec" not in str(error.value)


@pytest.mark.parametrize("pattern", [".*", ".+", "https?://.*", r"https://.*\.vercel\.app"])
def test_cors_regex_letting_in_foreign_sites_stops_startup(
    monkeypatch: pytest.MonkeyPatch, pattern: str
) -> None:
    """Wzorzec pasujący do obcych stron to gwiazdka z #60 zapisana inaczej.
    Każda aplikacja na vercel.app też jest obca - może ją postawić każdy."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGIN_REGEX", pattern)

    with pytest.raises(ValidationError, match="obce strony"):
        Settings(_env_file=None)


def test_narrow_cors_regex_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wzorzec z README - podglądy z Vercela z nazwą projektu - przechodzi."""
    pattern = r"^https://hackathon-matching-[a-z0-9-]+\.vercel\.app$"
    monkeypatch.setenv("CORS_ALLOWED_ORIGIN_REGEX", pattern)

    assert Settings(_env_file=None).cors_allowed_origin_regex == pattern


# --- Limity: da się je zmienić, ale nie poza bezpieczne granice (#57) ---


def test_defaults_match_the_measured_limits() -> None:
    settings = Settings(_env_file=None)

    assert (settings.min_team_size, settings.max_team_size) == (1, 20)
    assert settings.max_total_submissions == 3000
    assert settings.max_matched_participants == 2000


def test_limit_can_be_changed_within_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_TOTAL_SUBMISSIONS", "5000")

    assert Settings(_env_file=None).max_total_submissions == 5000


def test_blank_limit_means_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pusta zmienna w panelu to "nie ustawiono", a nie błąd parsowania liczby."""
    monkeypatch.setenv("MAX_TEAM_SIZE", "")

    assert Settings(_env_file=None).max_team_size == 20


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MAX_TOTAL_SUBMISSIONS", "100000"),
        ("MAX_MATCHED_PARTICIPANTS", "50000"),
        ("MAX_TEAM_SIZE", "200"),
        ("MIN_TEAM_SIZE", "0"),
        ("MAX_TOTAL_SUBMISSIONS", "dużo"),
    ],
)
def test_limit_outside_bounds_stops_startup(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    """Literówka w panelu nie może po cichu otworzyć z powrotem ataku z #57."""
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_min_team_size_above_max_stops_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIN_TEAM_SIZE", "6")
    monkeypatch.setenv("MAX_TEAM_SIZE", "4")

    with pytest.raises(ValidationError, match="MIN_TEAM_SIZE"):
        Settings(_env_file=None)


def test_errors_do_not_print_the_database_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """Komunikat błędu konfiguracji trafia do logów serwera. Pydantic domyślnie
    dokleja do niego wszystkie wczytane wartości - razem z DATABASE_URL, który
    zawiera hasło do bazy."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:sekretne-haslo@db.internal:5432/app")
    monkeypatch.setenv("MIN_TEAM_SIZE", "6")
    monkeypatch.setenv("MAX_TEAM_SIZE", "4")

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    message = str(error.value)
    assert "MIN_TEAM_SIZE" in message
    # Sprawdzamy mechanizm, nie tylko hasło: bez `hide_input_in_errors` hasło
    # ukrywa wyłącznie przypadek - pydantic skraca długi tekst w środku, a przy
    # krótszym adresie albo innej kolejności pól wypisałby je w całości.
    assert "input_value" not in message
    assert "sekretne-haslo" not in message


def test_printed_settings_do_not_show_the_database_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Obiekt ustawień może trafić do logu albo raportu błędu przez zwykłe
    wypisanie - adres bazy z hasłem nie może być jego częścią."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:sekretne-haslo@db.internal:5432/app")

    settings = Settings(_env_file=None)

    assert "sekretne-haslo" not in repr(settings)
    assert "sekretne-haslo" not in str(settings)
