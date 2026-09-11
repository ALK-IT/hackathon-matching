Matchowanie pojedynczych zgłoszeń uczestników w zespoły na hackathon — projekt studencki ALK. Monorepo: frontend (React) do przeglądu/edycji wyników matchowania + backend (FastAPI) z logiką dopasowania i API.

## Struktura repozytorium

```
hackathon-matching/
├── frontend/                  # React + Vite + TypeScript (lekki szkielet, bez Storybooka)
├── backend/                   # FastAPI + Python
├── .ai/specs/                 # Specyfikacje (spec-driven development)
├── scripts/ai-agents/         # Lokalni AI agenci: code/security/UX review
├── .github/                   # Workflows (CI, CodeQL, gitleaks, audyt zależności), szablony PR/issue, CODEOWNERS
├── .claude/                   # Konfiguracja Claude Code
├── docker-compose.yml         # Uruchomienie całości w Dockerze
├── SECURITY.md                # Polityka bezpieczeństwa
└── CONTRIBUTING.md            # Workflow pracy, branże, etykiety, kanban
```

## Sposób pracy (spec-driven development)

Przed implementacją nietrywialnej funkcjonalności powstaje krótki spec w [.ai/specs/](.ai/specs/README.md) (wzorowane na [open-mercato](https://github.com/open-mercato/open-mercato)). Pierwszy spec: [SPEC-001 — Hello World](.ai/specs/SPEC-001-hello-world.md). Pełny workflow pracy (branże, commity, PR, kanban, etykiety): [CONTRIBUTING.md](CONTRIBUTING.md).

W Claude Code dostępne są skille do tego procesu: `/new-spec` (analiza wymagań → spec), `/spec-to-issues` (spec → GitHub issues + kanban), `/spec-status` (audyt statusów speców vs PR-y/issues).

## Kanban / zadania / czas pracy

Tablica projektu (GitHub Projects): https://github.com/orgs/ALK-IT/projects/3
Issues: [github.com/ALK-IT/hackathon-matching/issues](https://github.com/ALK-IT/hackathon-matching/issues) — zgłoszenia przez szablony (bug / propozycja funkcjonalności).

Tablica ma pola **Szacowany czas (h)** i **Rzeczywisty czas (h)** na każdej karcie — wypełniaj przed startem i po zamknięciu zadania. Do granularnego logu w czasie: komentuj issue/PR w formacie `⏱ 2h - co robiłeś`; skill `/time-report` w Claude Code zlicza to per osoba i per zadanie.

## AI agenci (code review / security review / UX review)

Dodanie etykiety **`ai-review`** do pull requesta uruchamia (po odpaleniu lokalnego watchera) automatyczny przegląd: code review, security review, a dla zmian w `frontend/` — dodatkowo UX/design-system review. Działa lokalnie przez Claude Code (subskrypcja, bez kosztów per token w CI). Szczegóły: [scripts/ai-agents/README.md](scripts/ai-agents/README.md).

## Discord

Powiadomienia na Discordzie: nowy/zmergowany PR, nowe/zamknięte issue, czerwone CI lub nieudany deploy (workflow `discord-notify`), oraz — lokalnie — gdy agent AI skończy review. Wymaga webhooka Discorda: sekret repo `DISCORD_WEBHOOK_URL` (dla Actions) + lokalny `scripts/ai-agents/.env` (dla agentów AI). Instrukcja: [scripts/ai-agents/README.md](scripts/ai-agents/README.md#discord-opcjonalnie).

## Bezpieczeństwo

CodeQL, gitleaks (skan sekretów) i audyt zależności (`npm audit` / `pip-audit`) uruchamiają się automatycznie na każdym PR — patrz [SECURITY.md](SECURITY.md) po pełny opis mechanizmów i zasady zgłaszania podatności.

## Wymagania

- Node.js 20+
- Python 3.12+
- Docker + Docker Compose — do uruchomienia całości jedną komendą, a przy pracy lokalnej do samej bazy (chyba że masz własnego Postgresa 16)

## Uruchomienie w Dockerze

Najprostszy sposób odpalenia całości (frontend + backend):

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000 (dokumentacja API: http://localhost:8000/docs)

Zatrzymanie: `docker compose down`. Rebuild po zmianie zależności: `docker compose up --build`.

## Uruchomienie lokalne (bez Dockera)

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Frontend działa na http://localhost:5173 i domyślnie odpytuje backend pod `http://localhost:8000`. Inny adres ustawia się zmienną `VITE_API_URL` (czytana przy budowaniu, nie w trakcie działania).

### Backend

Backend potrzebuje Postgresa — bez niego wstanie, ale każde żądanie dotykające bazy skończy się błędem. Najprościej podnieść samą bazę z compose i zostawić resztę lokalnie:

```bash
# 1. baza (tylko ona, bez backendu i frontendu)
docker compose up -d postgres

# 2. zależności
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# 3. schemat bazy — bez tego tabele nie istnieją
alembic upgrade head

# 4. serwer
uvicorn app.main:app --reload
```

Backend słucha na http://localhost:8000, interaktywna dokumentacja API: **http://localhost:8000/docs**.

`DATABASE_URL` nie trzeba ustawiać — domyślna wartość wskazuje dokładnie na bazę z `docker-compose.yml`. Pełna lista zmiennych środowiskowych jest w [sekcji Deploy](#deploy).

## Przykłady API

Sprawdzone na lokalnie uruchomionym backendzie — odpowiedzi poniżej są prawdziwe, nie poglądowe.

**Zgłoszenie uczestnika:**

```bash
curl -X POST http://localhost:8000/api/submissions \
  -H 'Content-Type: application/json' \
  -d '{
    "full_name": "Anna Nowak",
    "email": "anna@example.com",
    "skills": ["python", "react"],
    "experience_level": "intermediate",
    "preferred_role": "backend",
    "availability": true
  }'
```

```json
{"id":1,"full_name":"Anna Nowak","email":"anna@example.com","skills":["python","react"],
 "experience_level":"intermediate","preferred_role":"backend","availability":true,
 "created_at":"2026-09-11T22:26:08.997021Z"}
```

**Błędne dane** dają `422` z komunikatami po polsku, gotowymi do pokazania w formularzu:

```json
{"detail":[{"loc":["body","full_name"],"msg":"Podaj imię i nazwisko.","type":"string_too_short"},
           {"loc":["body","email"],"msg":"Podaj poprawny adres e-mail, np. jan.kowalski@example.com.","type":"value_error"}]}
```

**Lista zgłoszeń** i **uruchomienie matchowania:**

```bash
curl http://localhost:8000/api/submissions

curl -X POST 'http://localhost:8000/api/match?team_size=3'
```

`POST /api/match` zwraca `201` z gotowymi zespołami i ich pełnym składem. Uwaga: **każde uruchomienie kasuje poprzedni podział** i liczy nowy — to nie jest operacja bezpieczna do powtórzenia w dowolnym momencie. Na pustej bazie odpowiada `409`.

Dopuszczalne wartości `experience_level` (`beginner`, `intermediate`, `advanced`) i `preferred_role` (`frontend`, `backend`, `fullstack`, `design`, `data`, `pm`, `other`) opisuje `/docs`.

## Testy

```bash
# frontend
cd frontend && npm run test -- --run

# backend
cd backend && pytest
```

## Deploy

- **Frontend** — Vercel, automatyczny deploy po merge do `main` (workflow `deploy-frontend`). Produkcja: https://hackathon-matching-chi.vercel.app
- **Backend** — Railway, automatyczny deploy po merge do `main` (workflow `deploy-backend`).

Wymagane sekrety repozytorium (Settings → Secrets and variables → Actions):

| Sekret | Do czego służy |
|---|---|
| `VERCEL_TOKEN` | Token dostępu Vercel |
| `VERCEL_ORG_ID` | ID organizacji Vercel |
| `VERCEL_PROJECT_ID` | ID projektu Vercel (frontend) |
| `RAILWAY_TOKEN` | Token dostępu Railway |
| `RAILWAY_SERVICE` | Nazwa/ID serwisu Railway (backend) |
| `DISCORD_WEBHOOK_URL` | Powiadomienia na Discordzie (opcjonalnie) |

Zmienne środowiskowe backendu (ustawiane w panelu Railway, nie w sekretach GitHuba):

| Zmienna | Domyślnie | Do czego służy |
|---|---|---|
| `DATABASE_URL` | lokalny Postgres z `docker-compose.yml` | Połączenie z bazą; `postgres://` i `postgresql://` są normalizowane do `+asyncpg` |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173`, `http://127.0.0.1:5173`, adres produkcyjny frontendu | Lista adresów po przecinku, którym przeglądarka pozwoli czytać odpowiedzi API. **Pusta wartość nie oznacza „wpuść wszystkich" — zostawia listę domyślną.** Po zmianie adresu frontendu trzeba ją zaktualizować, inaczej front dostanie błąd CORS |
| `CORS_ALLOWED_ORIGIN_REGEX` | wyłączone | Wzorzec dodatkowych adresów, np. podglądów z Vercela, które dostają adres per gałąź: `^https://hackathon-matching-[a-z0-9-]+\.vercel\.app$` |

## Zasady współpracy

Pełny opis w [CONTRIBUTING.md](CONTRIBUTING.md). W skrócie:

- Praca na branchach `feat/...` / `fix/...` / `chore/...`, zmiany trafiają do `main` przez pull request.
- Wymagane: 2 zatwierdzenia review (w tym code owners), przejście CI (`frontend-ci`, `backend-ci`), rozwiązanie wszystkich konwersacji.
- Zobacz [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md) i [CODEOWNERS](.github/CODEOWNERS) — zaktualizuj właścicieli kodu.

## Licencja

MIT — zobacz [LICENSE](LICENSE).
