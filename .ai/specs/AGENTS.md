# Zasady pracy ze specyfikacjami (dla ludzi i agentów AI)

- Każda nietrywialna funkcjonalność / zmiana architektury dostaje spec w `.ai/specs/` **przed** albo **w trakcie** pierwszej implementacji.
- Nazwa pliku: `SPEC-XXX-RRRR-MM-DD-krotki-tytul.md` (XXX = kolejny numer, 3 cyfry).
- Każdy spec zawiera: Kontekst/Problem, Rozwiązanie, Zakres (co wchodzi / co nie), Wpływ na frontend/backend, Alternatywy, Status.
- Status specu aktualizowany w nagłówku: `Proponowany` → `Zaakceptowany` → `Zaimplementowany` → (opcjonalnie) `Wycofany`.
- Nowy spec → dopisz wpis do tabeli w [README.md](README.md).
- Agent AI (np. Claude Code) pracujący nad nowym feature'em w tym repo powinien:
  1. Sprawdzić, czy istnieje już powiązany spec.
  2. Jeśli zmiana jest nietrywialna, a specu brak — zaproponować go przed dużą implementacją.
  3. Odnosić się do numeru specu w commitach/PR (`Spec: SPEC-00X`).
- Drobne poprawki (bugfix, literówki, refaktor bez zmiany zachowania) nie wymagają specu.

Zobacz też [CONTRIBUTING.md](../../CONTRIBUTING.md) i [.claude/CLAUDE.md](../../.claude/CLAUDE.md).
