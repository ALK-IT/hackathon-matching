---
name: spec-to-issues
description: Rozbija zaakceptowany spec z .ai/specs/ na konkretne GitHub issues (gh issue create), z etykietami i dodaniem do tablicy kanban. Użyj gdy spec jest gotowy do wdrożenia i trzeba go przełożyć na zadania na GitHubie.
---

# /spec-to-issues — spec → GitHub issues

Cel: przekształcić spec w `.ai/specs/` na konkretne, wykonywalne issues na GitHubie, gotowe do wzięcia z kanbanu.

## Kroki

1. **Znajdź spec.** Argument (`args`) to numer (`SPEC-003`) albo ścieżka do pliku. Jeśli brak argumentu, zapytaj który spec (pokaż listę z `.ai/specs/README.md`, preferuj status `Zaakceptowany`).

2. **Sprawdź status.** Jeśli spec ma status `Proponowany` (nie `Zaakceptowany`), zapytaj usera czy na pewno chce już tworzyć issues, czy najpierw zaakceptować spec.

3. **Rozbij na zadania.** Przeanalizuj sekcje "Zakres" i "Wpływ" specu i zaproponuj listę konkretnych, małych issues (każdy realny do zrobienia w 1 PR). Dla każdego określ:
   - Tytuł (konkretny, czasownikowy: "Dodaj endpoint X", nie "Backend stuff")
   - Krótki opis + odniesienie `Spec: SPEC-XXX`
   - Etykiety: `frontend` i/lub `backend`, plus `spec-needed` jeśli podzadanie samo w sobie jest na tyle duże, że zasługuje na własny sub-spec (rzadko)

4. **Pokaż listę userowi przed utworzeniem** (tytuły + jednolinijkowe opisy) — krótkie potwierdzenie, że lista ma sens, zanim zaczniesz tworzyć issues (to nieodwracalne, widoczne dla zespołu).

5. **Utwórz issues przez gh**, jedno na jedno:
   ```
   gh issue create --repo <owner>/<repo> --title "<tytuł>" --body "Spec: .ai/specs/<plik>.md`n`n<opis>" --label "<etykiety>"
   ```
   Repo określ przez `gh repo view --json nameWithOwner` jeśli nieznane z kontekstu.

6. **Dodaj każde utworzone issue do tablicy kanban**, jeśli projekt jest podpięty:
   ```
   gh project item-add <numer-projektu> --owner <org> --url <url-issue>
   ```
   Numer projektu i org znajdziesz przez `gh project list --owner <org>`. Jeśli brak dostępu/projektu — pomiń ten krok z ostrzeżeniem, nie przerywaj całości.

7. **Zaktualizuj changelog specu** — dopisz do sekcji "Changelog" w pliku specu datę i listę numerów utworzonych issues (np. `- 2026-07-24 — utworzono issues #12, #13, #14`).

## Zasady

- Nie twórz issues duplikujących już istniejące — sprawdź `gh issue list --repo <owner>/<repo> --search "SPEC-XXX in:body"` przed utworzeniem.
- Nie twórz więcej niż ~10 issues za jednym razem bez wyraźnego potwierdzenia usera — dla dużych speców zaproponuj podział na etapy.
- Jeśli `gh project item-add` zawiedzie (brak scope 'project'), zgłoś to jako ostrzeżenie i kontynuuj — issues i tak powstały.
