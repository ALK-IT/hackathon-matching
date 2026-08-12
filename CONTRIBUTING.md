# Jak pracujemy — hackathon-matching

## Branże

- `main` — chroniony, zawsze wdrażalny. Bez bezpośrednich commitów.
- `feat/<krotki-opis>` — nowa funkcjonalność
- `fix/<krotki-opis>` — poprawka błędu
- `chore/<krotki-opis>` — porządki, konfiguracja, zależności

## Cykl pracy

1. Sprawdź [kanban na GitHub Projects](https://github.com/orgs/ALK-IT/projects/3) — wybierz zadanie z kolumny `Todo`, przenieś do `In Progress`.
2. Jeśli zmiana jest nietrywialna — najpierw spec w [.ai/specs/](.ai/specs/README.md): użyj skilla `/new-spec` (analiza wymagań → plik specu), potem `/spec-to-issues` żeby rozbić go na issues na kanbanie (patrz [.ai/specs/AGENTS.md](.ai/specs/AGENTS.md)).
3. Nowa branch od `main`: `git checkout -b feat/nazwa-zadania`.
4. Commity w konwencji [Conventional Commits](https://www.conventionalcommits.org/): `feat: ...`, `fix: ...`, `docs: ...`, `chore: ...`.
5. Push, otwórz PR do `main` — użyj [szablonu PR](.github/PULL_REQUEST_TEMPLATE.md), odnieś się do issue i (jeśli dotyczy) do numeru SPEC.
6. CI (`frontend-ci`, `backend-ci`, `codeql`, `gitleaks`, `dependency-audit`) musi przejść. Wymagane 2 review + code owners.
7. Opcjonalnie: dodaj etykietę `ai-review` — lokalny agent AI zrobi code/security/UX review (patrz [scripts/ai-agents/README.md](scripts/ai-agents/README.md)).
8. Po mergu (squash) branch usuwany automatycznie. Przenieś zadanie na kanbanie do `Done`, wpisz **Rzeczywisty czas (h)** na karcie.

## Czas pracy

- Na każdej karcie kanbanu: pole **Szacowany czas (h)** (przed startem) i **Rzeczywisty czas (h)** (po zamknięciu).
- Granularny log: komentarz na issue/PR w formacie `⏱ 2h - co zrobione`, np. `⏱ 1.5h - endpoint /api/hackathons + testy`.
- `/time-report` (skill Claude Code) zlicza czas z komentarzy per osoba i per zadanie.

## Etykiety (labels)

| Etykieta | Znaczenie |
|---|---|
| `frontend` | Dotyczy `frontend/` |
| `backend` | Dotyczy `backend/` |
| `bug` | Błąd |
| `enhancement` | Nowa funkcjonalność |
| `documentation` | Dokumentacja / README / specy |
| `spec-needed` | Wymaga specu w `.ai/specs/` przed implementacją |
| `ai-review` | Uruchamia lokalnego agenta AI (code/security/UX review) na PR |
| `ai-reviewed` | Agent AI już przejrzał ten PR |
| `security` | Zgłoszenie/PR dotyczy bezpieczeństwa — patrz [SECURITY.md](SECURITY.md) |
| `priority: high` / `priority: medium` / `priority: low` | Priorytet |
| `good first issue` | Dobre na start dla nowej osoby w zespole |

## Skille do wymagań / spec-driven development

Dostępne w Claude Code w tym repo (`.claude/skills/`):

| Skill | Do czego |
|---|---|
| `/new-spec` | Analiza wymagań (pytania doprecyzowujące) → nowy plik w `.ai/specs/` |
| `/spec-to-issues` | Rozbija zaakceptowany spec na GitHub issues + kanban |
| `/spec-status` | Audyt: statusy speców vs rzeczywiste PR-y/issues |
| `/time-report` | Zlicza czas z komentarzy `⏱ Xh` per osoba/zadanie |

## Design system

Nowe współdzielone komponenty UI powstają w `frontend/src/design-system/` (+ `.stories.tsx` w Storybooku), nie duplikujemy przycisków/formularzy lokalnie w widokach. Kolory/spacing/typografia z `tokens.ts`, nie hardkodowane inline. Katalog: `npm run storybook` (w `frontend/`).

## Testy i jakość

- Frontend: `npm run lint`, `npm run test -- --run`, `npm run build` (patrz [README.md](README.md)).
- Backend: `ruff check .`, `black --check .`, `pytest` (patrz [README.md](README.md)).
- Bezpieczeństwo: CodeQL, gitleaks, `npm audit` / `pip-audit` — automatycznie w CI na każdym PR. Zasady: [SECURITY.md](SECURITY.md).
- Nie mergujemy z czerwonym CI.

## Discord

Kanał zespołu dostaje powiadomienia: nowy/zmergowany PR, nowe/zamknięte issue, czerwone CI, nieudany deploy, oraz (lokalnie) gotowy AI review. Setup: [scripts/ai-agents/README.md](scripts/ai-agents/README.md#discord-opcjonalnie).

## Docker

Pełne uruchomienie lokalne przez Docker opisane w [README.md](README.md#uruchomienie-w-dockerze).
