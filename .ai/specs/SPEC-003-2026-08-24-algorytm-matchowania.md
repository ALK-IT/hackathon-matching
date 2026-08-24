# SPEC-003: Algorytm matchowania — balans doświadczenia, ról i umiejętności

**Status:** Proponowany
**Data:** 2026-08-24
**Autor:** GreenM1010 (synteza dwóch równoległych implementacji, druga: dachowka)

## Kontekst / Problem

Baseline z #23 (`random_teams`) tasuje zgłoszenia i tnie je na kawałki — może
z tego wyjść zespół samych początkujących albo pięciu frontendowców bez nikogo
od backendu. Po #43 zgłoszenie ma profil (poziom doświadczenia, preferowana
rola, umiejętności jako lista), więc jest z czego balansować. Issue #24 wymaga
algorytmu, który to robi, oraz udokumentowania, jakie kryterium optymalizujemy.

Zespół — zgodnie ze swoją praktyką — wykonał zadanie w dwóch niezależnych
implementacjach i porównał je pomiarami na wspólnej siatce testowej; ten spec
opisuje wynik syntezy (PR #45).

## Proponowane rozwiązanie

Czysta funkcja `balanced_teams` w `app/matching/balanced.py` (bez bazy i HTTP),
działająca w czterech krokach — szczegóły operacyjne w
[README modułu](../../backend/app/matching/README.md):

1. **Rozmiary zespołów** — `team_sizes` z baseline (`team_size` to limit
   górny; rozmiary różnią się najwyżej o 1).
2. **Plan poziomów** — zachłanne wyrównywanie sum punktów doświadczenia
   po miejscach w zespołach (od najmocniejszego do najuboższego zespołu).
3. **Obsadzanie miejsc** — w obrębie poziomu wchodzi kandydat dopełniający
   zespół: najrzadsza rola, przy remisie najmniejsze pokrycie umiejętności.
4. **Naprawa wymianami** — zamiany par między zespołami przyjmowane, gdy
   ściśle obniżają jawną funkcję celu `objective`; strażnik odrzuca zamiany
   łamiące gwarancję nie-beginnera.

### Decyzje projektowe

1. **Hierarchia kryteriów: doświadczenie → role → umiejętności** (decyzja
   zespołu). Zakodowana wagami `objective` = 100000 × rozpiętość sum punktów
   + 1000 × Σ rozpiętości ról + 1 × duplikaty umiejętności — przy skali
   hackathonu hierarchia jest w praktyce ścisła.
2. **Punkty za poziom: 3/2/1, brak danych = 0.** `None` nie jest liczony jako
   nie-beginner (nie zgadujemy za uczestnika), a zespół z niewiadomymi dostaje
   na wyrównanie osoby o potwierdzonym poziomie.
3. **Gwarancja twarda:** jeśli osób powyżej poziomu beginner jest ≥ liczby
   zespołów, żaden zespół nie składa się z samych początkujących — pilnowana
   w planie poziomów i podczas wymian.
4. **`None` w roli = osobny koszyk bez gwarancji rozrzutu** — to brak danych,
   nie monokultura do rozbijania.
5. **Balans umiejętności = różnorodność w zespole** (kara za powtórzenia tej
   samej umiejętności), a nie rozrzut per-skill między zespołami — zespół
   „sami pythonowcy" jest problemem, rozkład pythona po sali nie.
6. **`objective` jest publiczne** jako propozycja punktu wyjścia dla metryki
   w #26 — algorytm optymalizuje dokładnie to, co będzie mierzone.
7. **Determinizm bez `rng`**; opcjonalny `rng` miesza wyłącznie kolejność
   wejścia (rozstrzyganie remisów), gwarancje obowiązują tak samo.

### Zmierzone własności (siatka 152 układów, 1064 pary rola×układ)

Rozpiętość sum doświadczenia średnio 0,53, nigdy > 1; rozrzut każdej
zadeklarowanej roli ≤ 1 w 99,8% przypadków (nigdy > 2); duplikaty
umiejętności o ~35% rzadsze niż w `random_teams`; mediana czasu 5 ms.

## Zakres

**W zakresie:**
- `app/matching/balanced.py` (kroki 1–4, `objective`, protokół `Participant`),
  README modułu, dwa pliki testów (zachowania + własności na siatkach).

**Poza zakresem:**
- `availability` — model ją ma, algorytm jeszcze nie używa (osobne issue).
- `fullstack` jako częściowe pokrycie frontendu i backendu.
- Twarde ograniczenia typu „te osoby chcą być razem".
- Endpoint uruchamiający matchowanie — #25. Finalna metryka jakości — #26.

## Wpływ

- **Frontend:** brak zmian.
- **Backend:** nowy kod wyłącznie w `app/matching/` + testy; zero zmian
  w API, warstwach serwis/repozytorium i zależnościach.
- **Baza danych / API:** brak zmian.

## Alternatywy rozważane

**Optymalizacja dokładna (ILP / OR-Tools).** Odrzucone: nowa ciężka zależność,
dokładny podział to problem NP-trudny, a przy skali hackathonu zachłanność
z naprawą daje wynik nieodróżnialny w praktyce.

**Rola jako kryterium nadrzędne przy sadzaniu.** Odrzucone pomiarem: układ
role-first potrafi złamać gwarancję nie-beginnera (dwaj najsilniejsi lądują
w jednym zespole przez parzystość rozdawania).

**Sama zachłanność, bez naprawy.** Odrzucone pomiarem: naprawa usuwa 97%
najgorszych rozrzutów ról (67→2) i poprawia rozpiętość doświadczenia
(0,72→0,53), kosztem ~5 ms.

**Wyrównywanie rozrzutu osób bez podanej roli.** Odrzucone: wymuszanie
rozrzutu „niewiadomych" walczyłoby z balansem zadeklarowanych ról
i doświadczenia, nie dając nic w zamian.

## Changelog

- 2026-08-24 — utworzono spec; implementacja w PR #45 (gałąź
  `feat/balanced-teams-combined`, synteza `feat/matching-balanced`
  i `feat/balanced-teams-experience-roles`).
