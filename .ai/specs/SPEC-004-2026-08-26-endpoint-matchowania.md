# SPEC-004: Endpoint uruchamiający matchowanie i zapis zespołów

**Status:** Proponowany
**Data:** 2026-08-26
**Autor:** dachowka

## Kontekst / Problem

Algorytmy z #23 (`random_teams`) i #24 (`balanced_teams`) są czystymi funkcjami
w `app/matching/` i żyją wyłącznie w testach — nikt spoza zespołu nie jest
w stanie ich uruchomić ani zobaczyć wyniku. Zgłoszenia są już w bazie (#19,
#43), więc brakuje jednego ogniwa: sposobu, żeby powiedzieć „ułóż zespoły
z tego, co masz" i zachować odpowiedź.

Wynik matchowania nie może też zostawać w pamięci pojedynczego żądania —
podział jest tym, wokół czego kręci się reszta produktu (przegląd i edycja
składów w UI, metryka jakości z #26), więc musi mieć swoje miejsce w bazie.

Zadanie: issue #25. SPEC-003 świadomie zostawił je poza swoim zakresem.

## Proponowane rozwiązanie

`POST /api/match?team_size=4&algorithm=balanced` → **201** z listą powstałych
zespołów wraz z pełnym składem.

Przepływ zgodny ze wzorcem repozytorium (router → serwis → repozytorium,
patrz CLAUDE.md); sam algorytm zostaje bez najmniejszej zmiany — endpoint
tylko go opakowuje:

1. **Router** (`app/routers/matching.py`) — waliduje parametry z query stringa
   i tłumaczy wyjątek serwisu na kod HTTP. Nie dotyka bazy ani algorytmu.
2. **Serwis** (`app/services/matching.py`) — `run_matching(session, team_size,
   algorithm)`: pobiera zgłoszenia, woła wybraną funkcję z `app/matching/`,
   zleca zapis, zatwierdza transakcję.
3. **Repozytorium** (`app/repositories/teams.py`) — jedyne miejsce z zapytaniami
   o zespoły: `clear_teams` i `create_teams`.

### Model danych

Nowa tabela `teams` (`id`, `created_at`) i kolumna `submissions.team_id`
(FK → `teams.id`, `NULL`, `ON DELETE SET NULL`, indeks).

### Decyzje projektowe

1. **`team_id` na zgłoszeniu zamiast tabeli łączącej** (issue dopuszczało oba).
   Kryterium akceptacji „każde zgłoszenie w dokładnie jednym zespole" pilnuje
   wtedy sam schemat — kolumna mieści jedną wartość. Tabela many-to-many
   dopuszczałaby stan, którego i tak musielibyśmy zabraniać osobnym
   ograniczeniem unikalności, a nie daje w zamian nic, czego potrzebujemy.
2. **Każde uruchomienie zastępuje poprzedni podział**, nie dokłada się do niego.
   Wynik matchowania to jedna odpowiedź na pytanie „jak dzielimy tych ludzi",
   a nie historia prób; kilka podziałów naraz łamałoby punkt 1 i wymagało
   dodatkowej decyzji, który z nich obowiązuje.
3. **Kasowanie i zapis w jednej transakcji.** Gdyby algorytm albo zapis
   wywrócił się po zatwierdzonym kasowaniu, zostalibyśmy z bazą bez zespołów
   i bez wyniku. Nieudany przebieg ma zostawić poprzedni podział nietknięty.
4. **`ON DELETE SET NULL`, nie `CASCADE`.** Zgłoszenie to dane od uczestnika,
   zespół — wynik algorytmu do przeliczenia. Kasowanie pierwszego razem
   z drugim byłoby utratą danych nie do odzyskania.
5. **`algorithm` jako zamknięty enum** (`balanced` | `random`) — wartość
   z query stringa wskazuje funkcję do uruchomienia, więc nie ma prawa być
   dowolnym tekstem (SECURITY.md). `random` zostaje w API celowo: bez punktu
   odniesienia nie da się na żywych danych pokazać, co daje balansowanie (#26).
6. **`team_size` w zakresie 1–20, domyślnie 4.** Dolna granica to kontrakt
   `team_sizes` — API go nie zaostrza, tylko nie łamie; górna odsiewa wartości
   bez związku z hackatonem.
7. **POST, mimo braku ciała żądania.** Wywołanie zmienia stan (kasuje stary
   podział, zapisuje nowy), a GET musi być bezpieczny do powtórzenia.
8. **Pusta baza → 409, nie 500 ani puste 201.** Żądanie jest poprawne, zawodzi
   stan aplikacji, a klient wie, co zrobić.

## Zakres

**W zakresie:**
- Model `Team` + kolumna `Submission.team_id` + migracja Alembic.
- `app/repositories/teams.py`, `app/services/matching.py`,
  `app/routers/matching.py`, schemat `TeamOut`, enum `MatchingAlgorithm`.
- Polskie komunikaty walidacji dla parametrów query (`app/errors.py`).
- Testy integracyjne całej drogi: POST zgłoszeń → POST /api/match → pokrycie
  uczestników, trwałość zapisu, zastąpienie poprzedniego podziału.

**Poza zakresem:**
- `GET /api/teams` i widok wyników na froncie — osobne zadanie; endpoint
  zwraca podział od razu w odpowiedzi, więc da się go obejrzeć bez tego.
- Ręczna edycja składów (przenoszenie osoby między zespołami).
- Metryka jakości dopasowania (#26) — `objective` jest już publiczne.
- Uwierzytelnianie: endpoint zmienia stan globalny i docelowo należy do
  organizatora, nie do uczestnika. Cały backend jest dziś otwarty, więc
  ograniczenie dostępu to zadanie na poziomie całego API, nie tego endpointu.
- Nazwy zespołów, `availability` w algorytmie, historia przebiegów.

## Wpływ

- **Frontend:** brak zmian; dochodzi endpoint do wykorzystania w kolejnym
  zadaniu (widok zespołów).
- **Backend:** nowy router, serwis i repozytorium; `main.py` podpina router;
  `errors.py` uczy się parametrów query; bez nowych zależności.
- **Baza danych / API:** nowa tabela `teams`, nowa kolumna
  `submissions.team_id` (migracja `7356d2184cb5`). `GET /api/submissions`
  zwraca to samo co dotąd — `team_id` celowo nie wchodzi do `SubmissionOut`,
  żeby lista zgłoszeń nie zmieniła kontraktu dla frontu.

## Alternatywy rozważane

**Tabela łącząca `team_members` (many-to-many).** Odrzucone: dopuszcza stan
„jedno zgłoszenie w dwóch zespołach", który musielibyśmy blokować osobnym
ograniczeniem, a elastyczności, za którą się płaci, nie potrzebujemy.

**Dopisywanie kolejnych podziałów zamiast zastępowania (historia przebiegów).**
Odrzucone na teraz: wymaga pojęcia „przebieg matchowania" i decyzji, który
z podziałów jest obowiązujący. Da się dołożyć później (kolumna `run_id`),
gdy pojawi się realna potrzeba porównywania.

**Matchowanie w tle (kolejka/zadanie asynchroniczne).** Odrzucone: przy skali
hackathonu algorytm liczy się w milisekundach, a kolejka to nowa infrastruktura
i endpoint do odpytywania o status — koszt bez zysku.

**Zwracanie samych identyfikatorów zespołów.** Odrzucone: front i tak musiałby
dociągnąć każde zgłoszenie osobno, żeby pokazać cokolwiek sensownego.

## Changelog

- 2026-08-26 — utworzono spec; implementacja dla issue #25.
