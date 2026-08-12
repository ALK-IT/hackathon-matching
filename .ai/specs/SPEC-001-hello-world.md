# SPEC-001: Hello World — szkielet frontend/backend

**Status:** Zaimplementowany
**Data:** 2026-08-12
**Autor:** wygenerowano przez setup-alk-repo.ps1

## Kontekst / Problem

Nowy projekt studencki potrzebuje działającego od zera szkieletu: frontend rozmawiający z backendem, uruchamialny lokalnie i w Dockerze, żeby zespół miał punkt startowy zamiast pustego repo.

## Proponowane rozwiązanie

- Backend (FastAPI) wystawia `GET /api/hello` zwracające `{"message": "..."}`.
- Frontend (React + Vite) przy starcie odpytuje `VITE_API_URL + /api/hello` i wyświetla odpowiedź.
- CORS w backendzie otwarty (`*`) na etapie hello-world — do zawężenia w kolejnym spec przy pracy nad autentykacją/produkcją.

## Zakres

**W zakresie:**
- Endpoint `/api/hello` + test.
- Komponent `App.tsx` pokazujący status połączenia z backendem.
- Docker Compose uruchamiający oba serwisy lokalnie.

**Poza zakresem:**
- Autentykacja, baza danych, routing frontendowy — do kolejnych speców.

## Wpływ

- Frontend: `src/App.tsx`, zmienna środowiskowa `VITE_API_URL`.
- Backend: `app/main.py`, endpoint `/api/hello`.
- Baza danych / API: brak (na tym etapie).

## Alternatywy rozważane

- Statyczna strona bez wywołania do backendu — odrzucone, bo nie potwierdza integracji frontend↔backend.

## Changelog

- 2026-08-12 — utworzono i zaimplementowano spec (initial scaffold)
