---
name: new-spec
description: Analiza wymagań dla nowej funkcjonalności — zadaje pytania doprecyzowujące, tworzy spec w .ai/specs/ na bazie TEMPLATE.md i dopisuje go do indeksu. Użyj gdy ktoś opisuje nowy pomysł/feature i trzeba go przekuć w spec przed implementacją.
---

# /new-spec — analiza wymagań → spec

Cel: zamienić luźny opis funkcjonalności od użytkownika w konkretny, zapisany spec w `.ai/specs/`, zgodnie z metodologią spec-driven development tego repo (patrz `.ai/specs/AGENTS.md`).

## Kroki

1. **Zbierz kontekst z argumentu/rozmowy.** Jeśli podano `args`, potraktuj jako wstępny opis. Jeśli brakuje kluczowych informacji, zapytaj (użyj AskUserQuestion, jeśli dostępne, albo zwykłych pytań w tekście) o:
   - Jaki problem to rozwiązuje / dla kogo (użytkownik, persona)?
   - Zakres: co konkretnie wchodzi, a co świadomie zostaje poza?
   - Wpływ: frontend, backend, baza danych/API — czego dotyczy?
   - Ograniczenia (czas, technologia, zależności od innych speców)?
   - Jak sprawdzić, że jest zrobione (kryteria akceptacji)?

   Nie zadawaj więcej niż 3-4 pytania na raz. Jeśli user w opisie już odpowiedział na coś — nie pytaj ponownie.

2. **Ustal numer specu.** Przejrzyj pliki w `.ai/specs/` pasujące do `SPEC-###-*.md`, weź najwyższy numer +1 (3 cyfry, np. `SPEC-004`).

3. **Utwórz plik** `.ai/specs/SPEC-{numer}-{RRRR-MM-DD}-{krotki-slug}.md` na bazie struktury z `.ai/specs/TEMPLATE.md`, wypełniony zebranymi informacjami. Status początkowy: `Proponowany`.

4. **Zaktualizuj indeks** — dopisz wiersz do tabeli w `.ai/specs/README.md` (numer, tytuł, status, link do pliku).

5. **Podsumuj** dla użytkownika: co powstało, gdzie, i zapytaj czy:
   - od razu rozbić spec na issues (`/spec-to-issues`),
   - czy najpierw chce go przejrzeć/zmienić.

## Zasady

- Drobne zmiany (bugfix, refaktor bez zmiany zachowania) NIE dostają specu — powiedz to userowi zamiast tworzyć zbędny plik.
- Nie zgaduj kryteriów akceptacji ani zakresu, jeśli user ich nie podał i nie da się ich sensownie wywnioskować — dopytaj.
- Nie twórz automatycznie issues ani commitów — to osobny krok (`/spec-to-issues`), user decyduje kiedy.
