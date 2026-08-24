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
Krok 4 optymalizuje dokładnie tę funkcję, a #26 może jej użyć jako punktu
wyjścia do porównywania algorytmów - mierzymy wtedy to, co optymalizujemy.

Zmierzone na siatce testowej (152 układy, 1064 pary rola × układ), po kroku 4:
rozpiętość sum punktów średnio 0,53 i nigdy więcej niż 1; rozrzut ról ≤ 1
w 99,8% przypadków (nigdy > 2); powtórzenia umiejętności o ~35% rzadsze niż
w `random_teams`; mediana czasu 5 ms.

### Gwarancje (pilnowane przez testy w `tests/test_matching_balanced.py`)

- każde zgłoszenie w dokładnie jednym zespole, żaden zespół nie jest pusty
  i nie przekracza limitu, rozmiary różnią się najwyżej o jedną osobę;
- jeśli osób o poziomie wyższym niż początkujący jest co najmniej tyle, ile
  zespołów, **żaden zespół nie składa się z samych początkujących**;
- rozrzut sum punktów jest nie większy niż w `random_teams` na tych samych
  danych (test porównawczy na 50 losowych zestawach);
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
Metryka do porównywania algorytmów powstanie w #26.
