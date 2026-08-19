# SPEC-002: Endpoint przyjmujący zgłoszenia uczestników

**Status:** Proponowany
**Data:** 2026-08-18
**Autor:** GreenM1010

## Kontekst / Problem

Po SPEC-001 backend miał wyłącznie endpointy zwracające stałe napisy, a po issue #17 doszły
model `Submission` i tabela `submissions` w bazie. Brakuje ogniwa pośredniego: **nie ma
żadnego sposobu, żeby cokolwiek do tej tabeli trafiło**. Formularz frontendowy (#20) nie ma
dokąd wysyłać danych, a algorytm dopasowania (#23) nie ma czego dopasowywać.

Drugi, ważniejszy powód dla tego specu: to pierwsze zadanie wymagające warstwowania
opisanego w `CLAUDE.md`. Dotąd cały backend mieścił się w jednym pliku `main.py`. Struktura
katalogów i podział odpowiedzialności powstające przy tym zadaniu staną się wzorcem dla
kolejnych endpointów, więc decyzje warto zapisać, zanim ktoś zrobi #19 inaczej.

## Proponowane rozwiązanie

Endpoint `POST /api/submissions` zbudowany w trzech warstwach, zgodnie z `CLAUDE.md`:

| Warstwa | Plik | Odpowiedzialność |
|---|---|---|
| Router | `app/routers/submissions.py` | HTTP: odbiór żądania, kod odpowiedzi. Zero logiki, zero SQL |
| Serwis | `app/services/submissions.py` | Granica transakcji, błędy dziedzinowe |
| Repozytorium | `app/repositories/submissions.py` | Jedyne miejsce sięgające do bazy |

Schematy pydantic (`SubmissionCreate`, `SubmissionOut`) w `app/schemas.py`.

### Decyzje warte zapisania

1. **Routery mieszkają w osobnym pakiecie `app/routers/`**, nie w `main.py`. Ten ostatni
   pozostaje miejscem składania aplikacji, nie definiowania endpointów.
2. **Transakcję zatwierdza serwis.** Repozytorium robi `flush` (żeby baza nadała `id`
   i `created_at`), ale nie `commit` — o powodzeniu całej operacji wie dopiero warstwa wyżej.
3. **Duplikat e-maila wykrywamy przez próbę zapisu**, a nie wcześniejsze sprawdzenie
   „czy istnieje". Sprawdzenie z wyprzedzeniem ma wyścig: dwa równoległe żądania mogą oba
   je przejść. Ograniczenie unikalności w bazie jest jedynym miejscem, którego nie da się oszukać.
4. **Błędy dziedzinowe to własne wyjątki serwisu** (`DuplicateEmailError`), które router
   tłumaczy na kody HTTP. Dzięki temu serwis nie wie nic o HTTP i da się go użyć poza API.
5. **Repozytorium przyjmuje model pydantic** zamiast osobnych argumentów. Wiąże to warstwę
   bazy ze schematem API — świadomy kompromis na rzecz czytelności przy jednym konsumencie.
6. **Testy podmieniają sesję przez `dependency_overrides`** (`tests/conftest.py`), zamiast
   modyfikować kod produkcyjny. Sesja testowa nie używa puli połączeń, bo `TestClient`
   uruchamia każde żądanie we własnej pętli zdarzeń, a połączenie asyncpg jest przypisane
   do pętli, w której powstało.

## Zakres

**W zakresie:**
- Endpoint `POST /api/submissions` przyjmujący `SubmissionCreate`, zwracający `SubmissionOut` ze statusem 201.
- Schematy pydantic z walidacją: poprawny e-mail, niepuste `full_name`, górne limity długości.
- Trzy warstwy (router, serwis, repozytorium) jako wzorzec dla kolejnych zasobów.
- Duplikat e-maila zwracany jako 409 z czytelnym komunikatem, nie 500.
- Testy: happy path, błędny e-mail, puste `full_name`, duplikat.

**Poza zakresem:**
- Odczyt listy zgłoszeń — issue #19.
- Formularz frontendowy — issue #20.
- Rozszerzenie modelu o pola profilu uczestnika — issue #22.
- Uwierzytelnianie i autoryzacja: endpoint jest otwarty, bo zgłoszenie wysyła osoba z zewnątrz.
- Ograniczanie liczby żądań, paginacja, edycja i usuwanie zgłoszeń.

## Wpływ

- **Frontend:** brak zmian. Spec ustala kontrakt, z którego skorzysta #20.
- **Backend:** nowe pakiety `app/routers/`, `app/services/`, `app/repositories/`, nowy
  `app/schemas.py`, rejestracja routera w `app/main.py`. Do `requirements.txt` dochodzi
  dodatek `pydantic[email]` wymagany przez `EmailStr`.
- **Baza danych / API:** schemat bazy bez zmian (tabela powstała w #17). W API przybywa
  jeden endpoint.

## Alternatywy rozważane

**Endpoint bezpośrednio w `main.py`.** Odrzucone: przy kilkunastu endpointach z backlogu
plik rósłby bez końca, a `CLAUDE.md` wprost wskazuje warstwowanie.

**Sprawdzenie, czy e-mail istnieje, przed zapisem.** Odrzucone z powodu wyścigu opisanego
w decyzji 3. Dodatkowo to jedno zapytanie do bazy więcej przy każdym zgłoszeniu.

**Repozytorium przyjmujące osobne argumenty zamiast modelu pydantic.** Czystsze pod względem
rozdzielenia warstw, ale przy jednym konsumencie to przedwczesna abstrakcja. Do zmiany, gdy
pojawi się drugie miejsce tworzące zgłoszenia — na przykład import z pliku.

**Zwracanie 400 przy duplikacie.** Kryteria akceptacji dopuszczają 400 albo 409. Wybrano 409,
bo precyzyjniej opisuje sytuację: żądanie jest poprawne, ale koliduje z aktualnym stanem zasobu.

## Changelog

- 2026-08-18 — utworzono spec. Implementacja na gałęzi `feat/post-submissions`, issue #18.
