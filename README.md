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
- Docker + Docker Compose (opcjonalnie, do uruchomienia całości jedną komendą)

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

### Backend

```bash
cd backend
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

## Konto organizatora

Konta organizatorów są podstawą logowania opisanego w [SPEC-005](.ai/specs/SPEC-005-2026-09-11-autoryzacja-organizatora.md). **Na razie istnieje sam model i skrypt** — logowanie powstaje w #120, a ochrona endpointów w #54 i #55, więc dziś założone konto jeszcze nigdzie się nie przydaje.

Kont **nie da się założyć przez API** i nie będzie takiej możliwości — endpoint rejestracji byłby najkrótszą drogą do tego, żeby ktoś z zewnątrz zrobił sobie konto administratora. Jedyna droga prowadzi przez serwer:

```bash
cd backend
python -m scripts.create_organizer
```

Skrypt zapyta o adres e-mail i hasło (hasło nie jest widoczne przy wpisywaniu i trzeba je powtórzyć). Wymagane minimum to **12 znaków**; hasła zawierające oczywiste fragmenty w rodzaju `admin` czy `hackathon` są odrzucane.

Hasła nie podaje się argumentem ani zmienną środowiskową — argumenty widać w `ps` i zostają w historii powłoki.

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
