# hackathon-matching

Projekt studencki ALK. Monorepo: React (frontend) + FastAPI (backend).

## Struktura

- `frontend/` — React + Vite + TypeScript. Deploy: Vercel (auto na push do `main`). Komponenty UI w `src/design-system/` (Storybook), nie duplikuj ich lokalnie w widokach.
- `backend/` — FastAPI + Python 3.12. Deploy: Railway (auto na push do `main`).
- `scripts/ai-agents/` — lokalni agenci AI (code/security/UX review), triggerowani etykietą `ai-review` na PR.

## Komendy

Frontend (`cd frontend`):
- `npm ci` — instalacja zależności
- `npm run dev` — serwer developerski
- `npm run lint` — lint
- `npm run test -- --run` — testy
- `npm run build` — build produkcyjny

Backend (`cd backend`):
- `pip install -r requirements-dev.txt` — instalacja zależności
- `uvicorn app.main:app --reload` — serwer developerski
- `ruff check .` — lint
- `black --check .` — formatowanie
- `pytest` — testy

Frontend — design system / katalog komponentów: `npm run storybook` (w `frontend/`).

Całość przez Docker: `docker compose up --build` (frontend: http://localhost:5173, backend: http://localhost:8000/docs). Patrz [README.md](../README.md#uruchomienie-w-dockerze).

## Spec-driven development

Przed implementacją nietrywialnej funkcjonalności / istotnej zmiany architektury: sprawdź i/lub utwórz spec w [.ai/specs/](../.ai/specs/README.md) (wzorowane na [open-mercato](https://github.com/open-mercato/open-mercato)). Zasady: [.ai/specs/AGENTS.md](../.ai/specs/AGENTS.md). Drobne fixy/refaktory nie wymagają specu.

Skille do tego procesu: `/new-spec` (analiza wymagań → spec), `/spec-to-issues` (spec → GitHub issues + kanban), `/spec-status` (audyt statusów speców vs PR-y/issues), `/time-report` (czas pracy z komentarzy `⏱ Xh`). Gdy user opisuje nowy pomysł/feature bez odniesienia do istniejącego specu, rozważ zaproponowanie `/new-spec` zamiast implementować od razu.

## Czas pracy i Discord

Kanban ma pola Szacowany/Rzeczywisty czas (h); granularny log przez komentarze `⏱ Xh - opis` na issues/PR, agregowane przez `/time-report`. Powiadomienia zespołu (PR, issues, CI/deploy, AI review) idą na Discord — konfiguracja w [scripts/ai-agents/README.md](../scripts/ai-agents/README.md#discord-opcjonalnie).

## Bezpieczeństwo (priorytet)

- Traktuj bezpieczeństwo jako wymóg pierwszej klasy, nie dodatek na koniec — patrz [SECURITY.md](../SECURITY.md).
- Waliduj/sanityzuj wszystkie dane wejściowe (formularze, query params, body żądań).
- Nigdy nie commituj kluczy/haseł/tokenów — `.env` jest w `.gitignore`, sekrety tylko przez GitHub Secrets.
- Nowe zależności — zwracaj uwagę na CI (`dependency-audit`, `codeql`, `gitleaks`) na PR; nie ignoruj czerwonych wyników tych workflowów.
- Endpointy backendu — zawsze rozważ autoryzację/uwierzytelnianie, nie zakładaj zaufanego klienta.

## Zasady pracy

- Pełny opis przepływu pracy: [CONTRIBUTING.md](../CONTRIBUTING.md) (branże, etykiety, kanban, konwencja commitów).
- Zmiany przez pull request na `main` — branch chroniony (2 review, wymagane statusy CI, rozwiązane konwersacje, linear history).
- CI (`frontend-ci`, `backend-ci`, `codeql`, `gitleaks`, `dependency-audit`) musi przejść przed mergem.
- Nie commitować sekretów/kluczy — używać GitHub Secrets.
