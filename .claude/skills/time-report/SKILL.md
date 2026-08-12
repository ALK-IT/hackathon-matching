---
name: time-report
description: Zlicza czas spędzony na zadaniach z komentarzy na GitHubie (konwencja "⏱ Xh - opis" na issues/PR), agreguje per osoba i per zadanie. Użyj do raportu czasu pracy zespołu (np. na potrzeby prowadzącego).
---

# /time-report — raport czasu pracy

Cel: zebrać rozproszone wpisy czasu (komentarze z konwencją `⏱ Xh - opis`) z issues i PR-ów tego repo i pokazać zagregowany raport — kto ile poświęcił i na co.

Uzupełnia pola **Szacowany czas (h)** / **Rzeczywisty czas (h)** na tablicy kanban (te są ręcznie wypełniane per-karta na poziomie całego zadania; ten skill daje granularny log w czasie, kto/kiedy/ile).

## Kroki

1. Ustal repo: `gh repo view --json nameWithOwner`.
2. Pobierz wszystkie komentarze do issues i PR-ów (GitHub traktuje PR-y jako issues w tym API):
   ```
   gh api repos/<owner>/<repo>/issues/comments --paginate --jq '.[] | {author: .user.login, body: .body, url: .html_url, created_at: .created_at}'
   ```
3. Z każdego komentarza wyciągnij wpisy pasujące do wzorca `⏱\s*([\d.]+)\s*h` (jeden komentarz może mieć więcej niż jeden wpis czasu — rzadko, ale obsłuż).
4. Zbierz też numer issue/PR z URL-a komentarza (żeby zgrupować per zadanie) i, jeśli w treści issue/PR jest odniesienie do `SPEC-\d{3}`, dociągnij je (`gh issue view <numer> --json title,body` / `gh pr view`).
5. Zagreguj i pokaż dwie tabele w odpowiedzi (nie zapisuj do pliku, chyba że user prosi):

   **Czas per osoba:**

   | Osoba | Suma godzin | Liczba wpisów |
   |---|---|---|

   **Czas per zadanie:**

   | # | Tytuł | Spec | Suma godzin |
   |---|---|---|---|

6. Jeśli ktoś z aktywnych uczestników repo (autorzy commitów/PR-ów) ma zero wpisów czasu — wypisz to jako uwagę ("brak logowania czasu od: ...").

## Zasady

- To tylko raport (odczyt) — nie modyfikuj komentarzy, nie twórz nowych.
- Jeśli w repo nie ma jeszcze żadnych wpisów `⏱`, powiedz to wprost i przypomnij konwencję (patrz CONTRIBUTING.md) zamiast zwracać pusty raport bez kontekstu.
- Godziny sumuj z dokładnością do 0.25h (kwadrans), nie zaokrąglaj w dół/górę bez potrzeby.
