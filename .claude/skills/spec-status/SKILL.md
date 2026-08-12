---
name: spec-status
description: Audytuje .ai/specs/ — dla każdego specu sprawdza status deklarowany vs rzeczywisty stan (powiązane PR-y/issues/commity), raportuje rozjazd dokumentacji z kodem. Użyj okresowo albo przed planowaniem, żeby sprawdzić czy specy są aktualne.
---

# /spec-status — audyt speców vs rzeczywistość

Cel: wykryć rozjazd między tym co deklarują pliki w `.ai/specs/` (status w nagłówku) a tym, co faktycznie dzieje się w repo (GitHub issues/PR-y/commity).

## Kroki

1. **Zbierz specy.** Wylistuj wszystkie pliki `.ai/specs/SPEC-*.md`, dla każdego wyciągnij: numer, tytuł, zadeklarowany `Status` z nagłówka.

2. **Dla każdego specu sprawdź powiązania na GitHubie** (repo z `gh repo view --json nameWithOwner`):
   - `gh issue list --repo <owner>/<repo> --search "SPEC-XXX in:body" --state all`
   - `gh pr list --repo <owner>/<repo> --search "SPEC-XXX in:body" --state all`

3. **Wykryj rozjazdy**, np.:
   - Status `Zaimplementowany`, ale brak jakiegokolwiek powiązanego PR-a → prawdopodobnie status jest błędny albo referencja do specu zgubiła się w PR-ach.
   - Status `Proponowany`/`Zaakceptowany`, ale istnieje już zamknięty/zmergowany PR z odniesieniem → spec powinien być oznaczony jako `Zaimplementowany`.
   - Spec bez żadnych powiązanych issues/PR-ów starszy niż ~2 tygodnie → flaguj jako "porzucony / do przeglądu".

4. **Raportuj w tabeli** (w odpowiedzi, nie zapisuj automatycznie do pliku):

   | Spec | Status w pliku | Powiązane PR/issue | Uwaga |
   |---|---|---|---|

5. **Zaproponuj konkretne poprawki statusów** (np. "SPEC-002 → zmienić na Zaimplementowany, PR #18 zmergowany"), ale **nie edytuj plików automatycznie** — zapytaj usera, czy ma to zastosować, i wprowadź zmiany dopiero po potwierdzeniu.

## Zasady

- To jest audyt/raport, nie automatyczna korekta — nie zmieniaj plików speców bez potwierdzenia usera.
- Jeśli repo nie ma jeszcze żadnych PR-ów/issues (świeży projekt) — powiedz to wprost zamiast zgłaszać fałszywe rozjazdy.
