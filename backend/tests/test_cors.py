"""Testy zawężenia CORS (#60).

Dwie warstwy: czytanie konfiguracji ze zmiennej środowiskowej i faktyczne
zachowanie aplikacji, bo błąd w którejkolwiek z nich kończy się tak samo -
API otwartym dla dowolnej strony albo zamkniętym dla własnego frontendu.
"""

from fastapi.testclient import TestClient

from app.main import DEFAULT_ALLOWED_ORIGINS, allowed_origins, app

client = TestClient(app)

# Origin, którego żadna sensowna konfiguracja nie dopuści - używany wszędzie
# tam, gdzie sprawdzamy odmowę.
FOREIGN_ORIGIN = "https://evil.example"

# Aplikacja skonfigurowała middleware przy imporcie, więc testy HTTP muszą
# pytać o tę samą listę, a nie o stałą domyślną - inaczej wywracałyby się
# u kogoś, kto ma ustawione CORS_ALLOWED_ORIGINS w swoim środowisku.
ALLOWED_ORIGIN = allowed_origins()[0]


def test_pusta_zmienna_zostawia_domyslne_originy() -> None:
    """Brak konfiguracji ma zamykać API na domyślnych adresach, nie otwierać."""
    assert allowed_origins("") == list(DEFAULT_ALLOWED_ORIGINS)
    assert allowed_origins("   ") == list(DEFAULT_ALLOWED_ORIGINS)
    assert allowed_origins(",,") == list(DEFAULT_ALLOWED_ORIGINS)


def test_lista_po_przecinku_z_biala_spacja() -> None:
    assert allowed_origins("https://a.example,  https://b.example ") == [
        "https://a.example",
        "https://b.example",
    ]


def test_koncowy_ukosnik_jest_obcinany() -> None:
    """Nagłówek Origin nigdy nie ma ukośnika na końcu, więc wpis z ukośnikiem
    nie dopasowałby się do niczego i wyglądał na awarię, a nie literówkę."""
    assert allowed_origins("https://a.example/") == ["https://a.example"]


def test_gwiazdka_nie_jest_juz_domyslna() -> None:
    """Sedno #60: żaden domyślny wpis nie może być wildcardem."""
    assert "*" not in DEFAULT_ALLOWED_ORIGINS


def test_wlasny_front_dostaje_naglowek_cors() -> None:
    response = client.get("/api/hello", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_obca_strona_nie_dostaje_naglowka_cors() -> None:
    """Odpowiedź powstaje (CORS nie blokuje serwera), ale bez nagłówka
    przeglądarka nie pozwoli obcej stronie odczytać jej treści."""
    response = client.get("/api/hello", headers={"Origin": FOREIGN_ORIGIN})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_preflight_z_wlasnego_frontu_przechodzi() -> None:
    """POST /api/submissions z JSON-em wymaga preflightu - bez niego formularz
    przestałby działać, więc to test regresji na zbyt ostre zawężenie."""
    response = client.options(
        "/api/submissions",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "POST" in response.headers["access-control-allow-methods"]


def test_preflight_z_obcej_strony_nie_dostaje_zgody() -> None:
    response = client.options(
        "/api/submissions",
        headers={
            "Origin": FOREIGN_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_metoda_spoza_listy_nie_dostaje_zgody() -> None:
    """DELETE nie jest jeszcze przez API używane - preflight ma je odrzucić,
    zamiast przepuszczać wszystko jak przy allow_methods=['*'].

    Odmowa wygląda tu inaczej niż przy obcym originie: origin jest poprawny,
    więc Starlette odsyła 400 "Disallowed CORS method" i nadal dokleja
    nagłówek allow-origin. Dla przeglądarki liczy się to, że DELETE nie ma go
    na liście allow-methods - i to sprawdzamy, zamiast szukać braku nagłówka.
    """
    response = client.options(
        "/api/submissions",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "DELETE",
        },
    )

    assert response.status_code == 400
    assert "DELETE" not in response.headers["access-control-allow-methods"]
