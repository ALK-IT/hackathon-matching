# Algorytmy dopasowania (`app/matching/`)

Czyste funkcje: dostają listę zgłoszeń, zwracają listę zespołów. Bez bazy,
bez HTTP — dzięki temu da się je testować i porównywać ze sobą na tych samych
danych. Warstwa `app/services/` będzie je tylko uruchamiać i zapisywać wynik.

Wspólne dla wszystkich wariantów: `team_size` to **limit górny**, nie rozmiar
docelowy. Liczbę i wielkość zespołów wylicza `baseline.team_sizes` — najmniej
zespołów, w których wszyscy się mieszczą, a ludzie rozłożeni po równo
(9 osób przy limicie 4 → trzy zespoły po 3, a nie 4 + 4 + 1).

## `baseline.random_teams` — punkt odniesienia

Losowa kolejność, równy podział. Nie zagląda do profilu uczestnika. Istnieje
po to, żeby było do czego porównywać kolejne algorytmy (issue #23).

## `balanced.balanced_teams` — poziom + rola (issue #24)

### Co optymalizujemy

1. **Rozkład doświadczenia.** Każdy poziom ma wagę: zaawansowany 3,
   średniozaawansowany 2, początkujący 1, brak danych 0. Algorytm wyrównuje
   **sumę punktów** między zespołami — nie liczbę osób danego poziomu, bo dwóch
   średniozaawansowanych bywa lepszym odpowiednikiem jednego zaawansowanego
   i jednego początkującego niż dowolny podział "po etykietach".
2. **Różnorodność ról.** Przy równym poziomie doświadczenia wchodzi osoba
   o roli, której w zespole jeszcze nie ma (`preferred_role`).
3. **Różnorodność umiejętności.** Rozjemca przy remisie w rolach: wygrywa
   kandydat o mniejszym pokryciu umiejętności już obecnych w zespole.

Kryteria są **leksykograficzne**, nie ważone: rola rozstrzyga dopiero
*w obrębie jednego poziomu*, więc dobór ról nigdy nie psuje balansu
doświadczenia. Kolejność jest zamierzona — najpierw skład "na papierze",
potem konkretni ludzie.

### Jak to działa (cztery kroki)

1. **Puste zespoły.** `team_sizes` daje same rozmiary — ile zespołów
   i po ile osób.
2. **Rozstawienie poziomów.** Poziomy zgłoszone przez uczestników idą od
   najmocniejszego; każdy trafia do zespołu o najniższej dotychczasowej sumie
   punktów, który ma jeszcze wolne miejsce (zachłanne wyrównywanie obciążenia,
   remisy: najpierw zespół z większą liczbą wolnych miejsc, potem indeks).
   Powstaje plan typu "ten zespół: zaawansowany + średni + początkujący".
3. **Obsadzenie miejsc.** Rundami (najpierw pierwsze miejsce każdego zespołu,
   potem drugie itd.), żeby żaden zespół nie wybierał tylko z resztek. Na
   miejsce o danym poziomie wchodzi kandydat z najrzadszą w tym zespole rolą,
   przy remisie — z najmniejszym pokryciem umiejętności.

4. **Naprawa wymianami.** Kroki 2-3 decydują po jednej osobie i nie wracają
   do podjętych decyzji - ostatnie miejsca nie mają już wyboru. Naprawa patrzy
   na skończony układ i przyjmuje każdą zamianę pary między zespołami, która
   ściśle obniża `objective`; zamiana łamiąca gwarancję nie-beginnera jest
   odrzucana nawet przy lepszym wyniku. Rozmiary zespołów nie mogą się przy
   tym zepsuć z konstrukcji (zamiany 1-za-1).

Przykład z issue: 3 × zaawansowany, 4 × średniozaawansowany, 2 × początkujący,
limit 4 → trzy zespoły po 3 osoby o sumach punktów 7 / 6 / 6.

### `objective` — wspólna miara układu

Jawna funkcja oceny (niższa = lepsza): `100000 × rozpiętość sum punktów
+ 1000 × Σ rozpiętości ról + 1 × powtórzenia umiejętności w zespołach`.
Wagi czynią hierarchię kryteriów w praktyce ścisłą przy skali hackathonu.
Krok 4 optymalizuje dokładnie tę funkcję. Metryka z #26 (sekcja niżej)
pokazuje ją obok nazwanych miar — trzy z nich to jej rozpisane składniki.

Zmierzone na siatce testowej (152 układy, 1064 pary rola × układ), po kroku 4:
rozpiętość sum punktów średnio 0,53 i nigdy więcej niż 1; rozrzut ról ≤ 1
w 99,8% przypadków (nigdy > 2); powtórzenia umiejętności o ~35% rzadsze niż
w `random_teams`; mediana czasu 5 ms.

### Gwarancje (pilnowane przez testy w `tests/test_matching_balanced.py`)

- każde zgłoszenie w dokładnie jednym zespole, żaden zespół nie jest pusty
  i nie przekracza limitu, rozmiary różnią się najwyżej o jedną osobę;
- jeśli osób o poziomie wyższym niż początkujący jest co najmniej tyle, ile
  zespołów, **żaden zespół nie składa się z samych początkujących**;
- rozrzut sum punktów jest w praktyce mniejszy niż w `random_teams` na tych
  samych danych (test porównawczy na 50 losowych zestawach). To obserwacja,
  nie gwarancja: naprawa wymianami utyka, gdy poprawa wymaga dwóch zamian
  naraz — przy sumach [6, 6, 4, 4] jedna zamiana daje co najwyżej
  [5, 6, 5, 4], czyli ten sam rozrzut. W porównaniu z #26 losowanie wygrywa
  w ten sposób w 1 zestawie na 3000;
- bez `rng` wynik jest deterministyczny; `rng` miesza tylko kolejność wejścia,
  czyli sposób rozstrzygania remisów — gwarancje wyżej obowiązują tak samo
  (naprawa wymianami też jest deterministyczna: stała kolejność skanu);
- wejściowa lista pozostaje nietknięta.

Testy własnościowe (siatki i agregaty) są w
`tests/test_matching_balanced_properties.py`.

### Czego (jeszcze) nie robi

Nie patrzy na `availability`, nie traktuje `fullstack` jako częściowego
pokrycia frontendu i backendu, nie zna twardych ograniczeń typu "te osoby chcą
być razem". Wyrównanie jest heurystyczne (zachłanny plan + lokalna naprawa wymianami
par), a nie optymalne — dokładny podział to problem NP-trudny, a naprawa nie
wykona rotacji trzech osób naraz. Przy skali hackatonu różnica jest pomijalna.
Jak mierzymy jakość podziału i porównujemy warianty — sekcja niżej (#26).

## `metrics.score_teams` — metryka jakości (issue #26)

Ocenia gotowy podział dowolnego algorytmu zestawem nazwanych miar. W każdej
**niżej = lepiej** — poza f, której kierunek czeka na #58:

| Miara | Co mówi |
|---|---|
| a) `experience_spread` | różnica sum punktów za doświadczenie między zespołami |
| b1) `teams_without_backend_pct`, b2) `teams_without_frontend_pct` | % zespołów bez nikogo z tą rolą; zależy też od danych — gdy backendowców jest mniej niż zespołów, część musi zostać bez nich |
| b3) `role_spread` | średnio po rolach: o ile różni się liczba osób z daną rolą między zespołami |
| c) `duplicate_skills_per_team` | powtórzone umiejętności na zespół |
| d) `size_spread` | różnica wielkości zespołów — miara **kontrolna**: oba algorytmy dzielą według `team_sizes`, więc wychodzi zawsze tak samo |
| e) `teams_without_experienced_pct` | % zespołów bez nikogo co najmniej średniozaawansowanego |
| f) `availability_spread` | różnica liczby osób bez pełnej dostępności (`availability=False`) między zespołami; **kierunek zależy od #58** |
| `objective` | liczba zbiorcza: funkcja celu `balanced_teams` |

Nie wszystkie miary są niezależne od algorytmu, i trzeba to wiedzieć, czytając
porównanie:

- **a, b3, c** to rozpisane na jednostki składniki `objective` —
  `balanced_teams` optymalizuje je wprost. Przewaga w nich pokazuje, że
  algorytm robi to, co ma robić, a nie że jest lepszy według zewnętrznej miary;
- **b1, b2, e** nie wchodzą do `objective` (e pilnuje gwarancja z #24);
- **f** jest dziś od algorytmu całkiem niezależna, **d** jest kontrolna.

`objective` to ocena algorytmu według jego **własnego** celu. `balanced_teams`
optymalizuje ją heurystycznie, więc prawie zawsze w niej wygrywa (przy 3000
zestawach dwie przegrane) — i ta wygrana sama niczego nie dowodzi.

### Porównanie algorytmów

```
python -m app.matching.compare                  # z katalogu backend/
python -m app.matching.compare --datasets 50 --seed 7
```

Oba algorytmy dostają każdy zestaw w identycznej postaci; skrypt podaje
średnie i bilans liczony zestaw po zestawie. Wynik dla ustawień domyślnych
(300 syntetycznych zestawów po 8–40 osób, limit 3–5, ziarno 2026):

```
miara (nizej = lepiej)                         random     balanced   balanced lepszy / remis / gorszy
a) rozrzut doswiadczenia (pkt)                   4.14         1.07     279 /    21 /     0
b1) % zespolow bez backendowca                  57.26        49.67     109 /   190 /     1
b2) % zespolow bez frontendowca                 55.32        46.77     123 /   175 /     2
b3) rozrzut rol (srednio na role)                1.40         0.88     281 /    19 /     0
c) powtorzone umiejetnosci / zespol              1.84         0.85     286 /     7 /     7
d) rozrzut wielkosci (kontrolna)                 0.68         0.68       0 /   300 /     0
e) % zespolow bez doswiadczonego                 2.49         0.11      51 /   249 /     0
f) rozrzut niepelnej dostepnosci (#58)           1.70         1.63      65 /   189 /    46
objective (wlasny cel algorytmu)            423791.63    113187.84     300 /     0 /     0
```

Jak to czytać:

- **a, b3, c** — wyraźna przewaga, prawie nigdy gorzej. To składniki
  `objective`, więc to przede wszystkim dowód, że algorytm robi, co ma robić;
- **b1, b2, e** — przewaga w miarach, których `objective` nie liczy. Remis
  w b1/b2 tylko czasem wymusza sam rozkład danych (gdy z daną rolą jest
  najwyżej jedna osoba — 59 ze 190 remisów w b1); częściej losowanie po prostu
  trafia w najlepsze możliwe pokrycie, co przy kilku zespołach jest łatwe.
  Zespół bez doświadczonej osoby powstaje u `balanced_teams` wyłącznie wtedy,
  gdy doświadczonych jest mniej niż zespołów (sprawdzone na tych samych danych);
- **d** — zawsze remis, zgodnie z założeniem miary kontrolnej;
- **f** — brak systematycznej różnicy w żadną stronę, bo algorytm nie patrzy
  na dostępność (#58). Kierunek tej miary nie jest jeszcze przesądzony: treść
  #58 mówi o zrównoważeniu takich osób, a komentarz przy kolumnie
  `availability` w `models.py` — o ich grupowaniu; przy grupowaniu potrzebna
  będzie inna miara, nie sama zmiana znaku;
- **objective** — wygrana prawie zawsze, bo to cel algorytmu; sama w sobie nie
  jest argumentem.

Test akceptacyjny w `tests/test_matching_metrics.py` sprawdza to samo na 40
zestawach; po podmianie `balanced_teams` na losowanie pada.
