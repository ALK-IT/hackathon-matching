"""Tłumaczenie błędów walidacji na komunikaty dla uczestnika.

Pydantic opisuje błędy po angielsku i językiem implementacji ("value is not
a valid email address: The part after the @-sign is not valid"). Front
pokazuje `msg` z odpowiedzi wprost, więc bez tego tłumaczenia polski
formularz odpowiada uczestnikowi po angielsku.
"""

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Komunikat dobieramy po nazwie pola, a nie po typie błędu z pydantica:
# uczestnika nie interesuje, czy adres odpadł na braku kropki, czy na braku
# małpy - w obu przypadkach ma zrobić dokładnie to samo.
FIELD_MESSAGES: dict[str, str] = {
    "full_name": "Podaj imię i nazwisko.",
    "email": "Podaj poprawny adres e-mail, np. jan.kowalski@example.com.",
    "skills": "Podaj od 1 do 20 umiejętności, każda o długości do 50 znaków.",
    "experience_level": "Wybierz poziom doświadczenia z listy.",
    "preferred_role": "Wybierz preferowaną rolę z listy.",
    "availability": "Zaznacz lub odznacz dostępność.",
}

DEFAULT_MESSAGE = "Niepoprawne dane w formularzu."


def _field_name(location: tuple[Any, ...]) -> str | None:
    """Wyciąga nazwę pola ze ścieżki błędu.

    Ścieżka wygląda jak ("body", "email") albo ("body", "skills", 0) dla
    błędu w konkretnej pozycji listy - w obu przypadkach interesuje nas
    drugi element.
    """
    if len(location) >= 2 and location[0] == "body":
        name = location[1]
        return name if isinstance(name, str) else None
    return None


def translate_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Zamienia błędy pydantica na polskie komunikaty.

    Zachowujemy kształt odpowiedzi FastAPI (lista z `loc`/`msg`/`type`),
    żeby front nie musiał się zmieniać, a `ctx` z oryginalnym wyjątkiem
    zostaje pominięty - bywa nieserializowalny do JSON-a.

    Powtórzenia usuwamy, bo jedno pole potrafi dać kilka błędów naraz
    (np. za krótkie i w złym formacie), a uczestnik zobaczyłby ten sam
    komunikat dwa razy.
    """
    translated: list[dict[str, Any]] = []
    seen: set[str] = set()

    for error in errors:
        field = _field_name(tuple(error.get("loc", ())))
        message = FIELD_MESSAGES.get(field or "", DEFAULT_MESSAGE)
        if message in seen:
            continue
        seen.add(message)
        translated.append(
            {
                "loc": list(error.get("loc", ())),
                "msg": message,
                "type": error.get("type", "value_error"),
            }
        )

    return translated


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Odpowiada na 422 tak samo jak FastAPI, tylko po polsku."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": translate_errors(exc.errors())},
    )
