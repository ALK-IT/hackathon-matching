# Specyfikacje — hackathon-matching

Ten projekt stosuje metodologię **spec-driven development**: przed implementacją nietrywialnej funkcjonalności lub istotnej zmiany architektonicznej powstaje krótka specyfikacja w tym katalogu.

Wzorowane na podejściu z [open-mercato](https://github.com/open-mercato/open-mercato) (`.ai/specs/`).

## Proces

1. Nowa funkcjonalność / istotna zmiana → `/new-spec` (skill Claude Code) przeprowadzi analizę wymagań i utworzy plik `SPEC-XXX-2026-08-12-krotki-tytul.md` na bazie [TEMPLATE.md](TEMPLATE.md). Można też zrobić to ręcznie.
2. Spec opisuje: problem, proponowane rozwiązanie, wpływ na frontend/backend, alternatywy.
3. Gdy spec ma status `Zaakceptowany` → `/spec-to-issues` rozbija go na konkretne issues na GitHubie i dodaje je do kanbanu.
4. Status specu: `Proponowany` → `Zaakceptowany` → `Zaimplementowany` (aktualizuj nagłówek pliku).
5. Pull request odnosi się do specu w opisie (patrz szablon PR) — agent AI (`ai-review`) ostrzeże, jeśli nietrywialny PR nie ma odniesienia do żadnego SPEC-a.
6. `/spec-status` — okresowy audyt: sprawdza, czy statusy speców zgadzają się z rzeczywistymi PR-ami/issues na GitHubie.

## Indeks specyfikacji

| # | Tytuł | Status | Plik |
|---|---|---|---|
| SPEC-001 | Hello World — szkielet frontend/backend | Zaimplementowany | [SPEC-001-hello-world.md](SPEC-001-hello-world.md) |
| SPEC-002 | Endpoint przyjmujący zgłoszenia uczestników | Proponowany | [SPEC-002-2026-08-18-post-submissions.md](SPEC-002-2026-08-18-post-submissions.md) |

Zasady utrzymania tego indeksu i współpracy z agentami AI: [AGENTS.md](AGENTS.md).
