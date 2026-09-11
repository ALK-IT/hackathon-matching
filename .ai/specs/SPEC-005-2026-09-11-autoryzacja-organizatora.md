# SPEC-005: Autoryzacja organizatora

**Status:** Zaakceptowany
**Data:** 2026-09-11
**Autor:** dachowka

## Kontekst / Problem

Całe API jest dziś publiczne. Nie ma w projekcie żadnego mechanizmu uwierzytelniania — ani zależności, ani `Depends`, ani niczego we frontendzie. Wynikają z tego dwa zgłoszenia o priorytecie `high`:

- **#54** — `POST /api/match` kasuje obecny podział na zespoły i liczy nowy (DELETE + INSERT). Każdy, kto zna adres backendu (jest publiczny na Railway), może w dowolnym momencie nadpisać wynik, choćby tuż przed ogłoszeniem składów.
- **#55** — `GET /api/submissions` zwraca imię, nazwisko, e-mail i umiejętności **każdego** zgłoszonego, w całości, bez auth i bez paginacji. To wyciek danych osobowych na skalę całej bazy do dowolnego anonimowego klienta.

Zawężenie CORS (#60) podniosło koszt najprostszego ataku z przeglądarki, ale CORS obowiązuje wyłącznie przeglądarki — `curl` wchodzi bez przeszkód. To nie zastępuje autoryzacji.

Łatanie tego punktowo, per endpoint, byłoby błędem: każda kolejna funkcja organizatorska (ręczna edycja wyników #69, historia przebiegów #72, eksport, powiadomienia #73) potrzebowałaby własnej, niespójnej ochrony. Potrzebny jest jeden mechanizm — to jest treść zadania nadrzędnego **#68**.

### Model zagrożenia

To nie jest panel administracyjny firmy ukryty w intranecie. **Atakujący to uczestnik tego samego hackathonu**: zna stos technologiczny, ma adres backendu, siedzi w tej samej sieci i ma motyw (przeliczyć zespoły po ogłoszeniu wyników, zobaczyć cudze zgłoszenia, podejrzeć skład konkurencji). Ma też czas i umiejętności. Projektujemy pod takiego przeciwnika, nie pod przypadkowego bota.

Z tego wynikają trzy konkretne ścieżki ataku, które spec musi zamknąć:

1. **Zgadywanie hasła** — najprostsze i najtańsze. Bez ograniczenia liczby prób słabe hasło pada w minuty.
2. **Kradzież tokena sesji** — realna droga to XSS przez dane, które wpisuje sam uczestnik (`full_name`, `skills`) i które organizator ogląda na liście zgłoszeń.
3. **Podrobienie tokena** — klasyka: zaakceptowanie tokena z podmienionym algorytmem podpisu albo bez weryfikacji terminu ważności.

## Proponowane rozwiązanie

Konta organizatorów w bazie, logowanie loginem i hasłem, token sesji w nagłówku `Authorization` o stałym, krótkim czasie życia.

### Model kont

Nowa tabela `organizers`: `id`, `email` (unikalny), `password_hash`, `created_at`. E-mail zapisywany małymi literami — ta sama konwencja, którą wprowadziło #59 dla zgłoszeń, żeby nie powielać pułapki z wielkością liter.

Hasła wyłącznie jako hash z biblioteki przeznaczonej do tego celu (`pwdlib[argon2]` — dziś rekomendowana przez dokumentację FastAPI — albo `passlib[bcrypt]` z kosztem ≥ 12). Nigdy własna kryptografia, nigdy hasło w kolumnie, nigdy hasło w logu.

**Pierwsze konto** zakłada skrypt uruchamiany ręcznie (`backend/scripts/create_organizer.py`), pytający o e-mail i hasło. Nie ma UI do zakładania kont i nie ma go w tym zakresie — organizatorów jest kilku i zakłada się ich raz. Wymagania skryptu:

- hasło czytane przez `getpass`, żeby nie trafiło na ekran ani do historii powłoki;
- **minimum 12 znaków**, odrzucenie haseł z krótkiej listy oczywistych (`admin`, `hackathon`, nazwa projektu);
- hasło nigdy nie trafia do repozytorium, do migracji ani do zmiennej środowiskowej.

### Logowanie

`POST /api/auth/login` przyjmuje `{email, password}`, zwraca `{access_token, token_type, expires_at}`.

Obrona przed zgadywaniem hasła (ścieżka ataku 1) — **w zakresie tego specu, nie odłożona do #74**:

- **Limit prób per konto i per adres IP**, z rosnącym opóźnieniem odpowiedzi po serii nieudanych prób. Konkretne progi do ustalenia przy implementacji, rząd wielkości: 5 prób, potem blokada na minuty.
- **Identyczna odpowiedź 401** dla nieistniejącego konta i dla błędnego hasła — bez tego da się sprawdzać, które adresy są zarejestrowane.
- **Stały czas odpowiedzi**: przy nieznanym e-mailu i tak wykonujemy weryfikację hasła wobec atrapy hasha. Inaczej różnica czasu odpowiedzi zdradza, czy konto istnieje, mimo identycznego komunikatu.
- **Logujemy nieudane próby** (e-mail i IP, nigdy hasło) — bez tego nikt nie zauważy trwającego ataku.

### Token sesji

Token to **JWT** podpisany HS256 sekretem z `AUTH_SECRET_KEY` (zmienna środowiskowa, na Railway jako sekret; długi, losowy, nigdy w repozytorium — pilnuje tego `gitleaks` w CI).

**Stały czas życia: `AUTH_TOKEN_TTL_HOURS`, domyślnie 8 h od zalogowania. Bez odnawiania.**

Token wygasa dokładnie osiem godzin po wydaniu, niezależnie od tego, co organizator w tym czasie robił. Po upływie terminu trzeba podać hasło ponownie.

Odrzuciliśmy sesję przesuwaną (odnawianie tokena przy każdym żądaniu), mimo że jest wygodniejsza, bo **znosi korzyść z krótkiego czasu życia w dokładnie tym scenariuszu, przed którym chcemy się bronić**: ktoś, kto przechwyci token, utrzyma go przy życiu w nieskończoność, wysyłając dowolne żądanie raz na kilka godzin. Sufit absolutny łagodziłby to, ale nie usuwał — a kosztem byłaby dodatkowa maszyneria po obu stronach.

Cena tej decyzji jest realna i świadoma: **sesja potrafi wygasnąć w środku pracy.** Ratuje to obsługa 401 po stronie frontu (niżej) — żądanie jest odrzucane, zanim cokolwiek zmieni w bazie, więc ponowne zalogowanie i powtórzenie kliknięcia niczego nie gubi.

W zamian konstrukcja jest prostsza: jeden limit zamiast dwóch, brak nagłówka odnawiającego, brak podmiany tokena po stronie frontu.

Obrona przed podrobieniem tokena (ścieżka ataku 3):

- Przy dekodowaniu **jawna lista dozwolonych algorytmów** (`algorithms=["HS256"]`). Bez tego biblioteka przyjmie algorytm wskazany przez sam token — to podręcznikowa dziura pozwalająca podstawić `none` albo pomylić HMAC z RSA.
- Weryfikacja `exp` **oraz** `iat`, z zerową tolerancją na przesunięcie zegara.
- W ładunku tokena wyłącznie `sub` (id organizatora), `exp` i `iat`. **JWT jest podpisany, ale NIE zaszyfrowany** — każdy, kto go ma, odczyta zawartość. Żadnych danych osobowych w środku.

### Ochrona endpointów

Zależność `require_organizer` w `app/dependencies.py`: czyta `Authorization: Bearer <token>`, weryfikuje podpis, oba terminy i istnienie konta, zwraca organizatora albo rzuca **401** (nie 403 — żądanie jest nieuwierzytelnione, a nie zabronione dla uwierzytelnionego; 403 zostaje na przyszłe role).

Za logowaniem: `POST /api/match` i `GET /api/submissions`.

Publiczne zostają: `POST /api/submissions` (uczestnik musi móc się zgłosić bez konta — to sedno produktu; kont uczestników nie ma i nie będzie w tym zakresie) oraz `/health`.

Sprawdzenie tokena jest **pierwsze w handlerze**, przed dotknięciem bazy. Dzięki temu żądanie z wygasłą sesją nie zdąży zacząć matchowania i nie zostawi bazy w połowie przeliczonej.

### Przechowywanie tokena po stronie frontu

Token trafia do `sessionStorage` (ginie po zamknięciu karty, nie jest współdzielony między kartami), a nie do `localStorage`.

Rozważaliśmy ciasteczko `HttpOnly`, które byłoby odporne na kradzież przez XSS (ścieżka ataku 2) — **odpadło z powodu technicznego, nie wygody**: frontend stoi na Vercelu, backend na Railway, czyli na różnych domenach. Ciasteczko działałoby wtedy tylko jako `SameSite=None`, co odbiera mu główną ochronę przed CSRF i wymagałoby dołożenia tokenów CSRF. Wróci do rozważenia, jeśli kiedyś oba trafią pod jedną domenę.

Skoro token jest osiągalny dla JavaScriptu, ścieżkę ataku 2 zamykamy u źródła:

- **Żadnego `dangerouslySetInnerHTML`** — React domyślnie escapuje treść, więc dane od uczestników (`full_name`, `skills`) renderują się bezpiecznie. Pilnuje tego reguła lintera, żeby nikt tego nie cofnął przypadkiem.
- Nagłówek **Content-Security-Policy** ograniczający źródła skryptów, jako druga warstwa na wypadek przeoczenia.
- 401 z dowolnego żądania natychmiast czyści token z `sessionStorage`.

### Paginacja `GET /api/submissions`

Parametry `limit` (domyślnie 50, zakres 1–200) i `offset` (domyślnie 0). Odpowiedź zmienia kształt z gołej tablicy na obiekt:

```json
{ "items": [ ... ], "total": 1247, "limit": 50, "offset": 0 }
```

`total` jest konieczne, żeby front wiedział, czy rysować przejście do kolejnej strony. Zmiana kształtu **zepsuje `SubmissionList.tsx`**, który od #82 ma twarde `if (!Array.isArray(data)) throw` — komponent musi zostać poprawiony w tym samym PR, inaczej lista wpadnie w stan błędu.

### Frontend

Nowy widok logowania organizatora. Po zalogowaniu widoczne: lista zgłoszeń z paginacją i przycisk matchowania. Widok uczestnika to od teraz wyłącznie formularz zgłoszenia z potwierdzeniem.

Wspólna obsługa odpowiedzi 401: czyszczenie tokena i powrót do ekranu logowania z komunikatem „Sesja wygasła, zaloguj się ponownie" — inaczej po wygaśnięciu organizator zobaczyłby pustą listę bez wyjaśnienia.

**Ostrzeżenie przed wygaśnięciem.** Skoro token nie odnawia się sam, sesja potrafi skończyć się w środku pracy. Na **10 minut** przed terminem pojawia się pasek z odliczaniem („Sesja wygaśnie za 9 minut") i przyciskiem prowadzącym do formularza logowania. Dziesięć minut, a nie pięć: tyle wystarczy, żeby spokojnie domknąć zadanie zamiast wpadać w pośpiech, a przy ośmiogodzinnej sesji pasek pokaże się raz na zmianę, więc się nie opatrzy.

Moment wygaśnięcia front zna z pola `expires_at` w odpowiedzi logowania — **backend nie musi nic dokładać**.

Przycisk prowadzi do formularza logowania, a **nie** odnawia tokena w tle. Automatyczne przedłużenie byłoby sesją przesuwaną tylnymi drzwiami, czyli tym, co odrzuciliśmy wyżej; ponowne podanie hasła jest świadomą decyzją człowieka, której skradziony token nie wywoła.

Pasek dostaje `role="status"`, zgodnie z rozwiązaniem z #64 — inaczej osoba korzystająca z czytnika ekranu dowie się o wygaśnięciu dopiero po fakcie.

### CORS

Do `allow_headers` w `app/main.py` dochodzi `"Authorization"`. Komentarz w tym miejscu (z #60) już to zapowiada.

## Zakres

**W zakresie:**

- Tabela `organizers` + migracja Alembic.
- Skrypt zakładający konto organizatora, z wymogiem siły hasła.
- `POST /api/auth/login`: weryfikacja hasła, stały czas odpowiedzi, identyczny 401 dla obu przyczyn, limit prób per konto i per IP, logowanie nieudanych prób.
- Token JWT o stałym, 8-godzinnym czasie życia, z pinowaniem algorytmu przy dekodowaniu.
- Zależność `require_organizer` zwracająca 401, wpięta w `POST /api/match` i `GET /api/submissions`.
- Paginacja `GET /api/submissions` (`limit`/`offset`, odpowiedź `{items, total, limit, offset}`).
- CORS: dopisanie `Authorization`.
- Frontend: widok logowania, przechowywanie tokena, ostrzeżenie z odliczaniem na 10 minut przed wygaśnięciem sesji, wspólna obsługa 401, dostosowanie `SubmissionList.tsx` do nowego kształtu odpowiedzi i paginacji, wysyłanie tokena z `MatchResults.tsx`, reguła lintera przeciw `dangerouslySetInnerHTML`, nagłówek CSP.
- Testy: logowanie poprawne i błędne, brak różnicy między „złe hasło" a „nie ma konta", limit prób, 401 bez tokena, z wygasłym, z podrobionym podpisem i z podmienionym algorytmem, wygaśnięcie tokena po ośmiu godzinach mimo aktywności, paginacja (domyślne wartości, granice, `total`), testy frontendu dla logowania i 401.
- Dokumentacja nowych zmiennych środowiskowych w README (`AUTH_SECRET_KEY`, `AUTH_TOKEN_TTL_HOURS`).

**Poza zakresem:**

- **Konta uczestników** — uczestnik nadal tylko wysyła formularz, bez rejestracji i bez hasła. Świadoma decyzja, zgodna z #68.
- Reset hasła i zmiana hasła z poziomu aplikacji (na razie przez ponowne uruchomienie skryptu).
- Magic link, 2FA, OAuth, logowanie kontem uczelnianym.
- Role inne niż organizator — wszyscy zalogowani mają te same uprawnienia; 403 zarezerwowane na później.
- Rate limiting **pozostałych** endpointów — to #74. W tym specu ograniczamy wyłącznie logowanie, bo tam ryzyko jest bezpośrednie.
- Unieważnianie pojedynczej sesji przed terminem (awaryjnie: zmiana `AUTH_SECRET_KEY`, która wylogowuje wszystkich).
- Edycja wyników matchowania (#69) i historia przebiegów (#72) — zbudują na tym mechanizmie, ale są osobnymi zadaniami.

## Wpływ

- **Frontend:** nowy widok logowania; moduł przechowywania tokena i pilnowania terminu ważności; wspólna obsługa 401; `SubmissionList.tsx` (kształt odpowiedzi, paginacja, token); `MatchResults.tsx` (token); `App.tsx` (podział na widok uczestnika i organizatora); konfiguracja lintera i CSP.
- **Backend:** nowe `app/routers/auth.py`, `app/services/auth.py`, `app/repositories/organizers.py`, `app/dependencies.py`, `backend/scripts/create_organizer.py`; zmiany w `routers/submissions.py` (auth + paginacja), `routers/matching.py` (auth), `services/submissions.py` i `repositories/submissions.py` (limit/offset + liczenie); `main.py` (CORS); dwie nowe zależności produkcyjne (biblioteka do hashowania, `PyJWT`) przechodzące przez istniejące `dependency-audit` i `codeql`.
- **Baza danych / API:** nowa tabela `organizers` (migracja). Zmiana kontraktu: `GET /api/submissions` zwraca obiekt zamiast tablicy i wymaga nagłówka — **zmiana łamiąca** dla każdego istniejącego klienta. Nowy `POST /api/auth/login`. `POST /api/match` wymaga nagłówka.

## Kryteria akceptacji

1. `GET /api/submissions` i `POST /api/match` bez nagłówka `Authorization` zwracają **401**, a nie dane ani 500.
2. Token wygasły, z podmienionym podpisem lub z podmienionym algorytmem (`none`) daje 401.
3. Token przestaje działać dokładnie po ośmiu godzinach od wydania, **mimo** nieprzerwanej aktywności — żadne żądanie go nie przedłuża.
4. `POST /api/auth/login` z błędnym hasłem i z nieistniejącym e-mailem zwracają **identyczną** odpowiedź 401, w porównywalnym czasie.
5. Po serii nieudanych prób kolejne są odrzucane lub opóźniane; fakt jest widoczny w logach.
6. Hasło nie występuje nigdzie w bazie, w logach ani w historii powłoki w postaci jawnej. Skrypt odrzuca hasło krótsze niż 12 znaków.
7. `POST /api/submissions` nadal działa bez logowania — uczestnik zgłasza się jak wcześniej.
8. `GET /api/submissions?limit=10&offset=0` zwraca najwyżej 10 pozycji i poprawne `total`; `limit` poza zakresem 1–200 daje 422.
9. Frontend: po zalogowaniu widać listę i przycisk matchowania; na 10 minut przed terminem pojawia się ostrzeżenie z odliczaniem; po wygaśnięciu sesji aplikacja wraca do ekranu logowania z czytelnym komunikatem, a token znika z `sessionStorage`.
10. CI zielone: `ruff`, `black`, `pytest`, `eslint`, `vitest`, `build`, `codeql`, `gitleaks`, `dependency-audit`.

## Alternatywy rozważane

- **Wspólny sekret w zmiennej środowiskowej** (jeden `ORGANIZER_TOKEN` dla wszystkich). Najtańszy wariant, zero tabel i migracji. Odrzucony: nie wiadomo, kto uruchomił matchowanie, a odebranie dostępu jednej osobie oznacza zmianę sekretu i wylogowanie wszystkich.
- **Magic link na e-mail** (sugerowany w #68 jako prostszy). Odrzucony na tym etapie: projekt nie wysyła dziś żadnej poczty, więc wymagałby najpierw dostawcy SMTP, szablonów i obsługi błędów wysyłki — czyli całego #73 przed auth.
- **Token w ciasteczku `HttpOnly`**. Bezpieczniejszy wobec XSS. Odrzucony z powodu technicznego: front i backend są na różnych domenach (Vercel i Railway), więc ciasteczko wymagałoby `SameSite=None` i dołożenia ochrony CSRF. Wraca do gry, jeśli oba znajdą się pod jedną domeną.
- **Token nieprzezroczysty w tabeli sesji** zamiast JWT. Pozwalałby unieważniać pojedynczą sesję. Odrzucony: druga tabela i zapytanie do bazy przy każdym żądaniu; przy suficie 7 dni i kilku organizatorach zysk jest niewielki. Gdyby doszły role albo konta uczestników, wart ponownego rozważenia.
- **Stały, długi czas życia tokena (7 dni).** Odrzucony: skradziony token działałby tydzień.
- **Sesja przesuwana** (token odnawiany przy każdym żądaniu, z sufitem absolutnym albo bez). Wygodniejsza — organizator nie zobaczyłby ekranu logowania w trakcie pracy — ale odrzucona świadomie: pozwala utrzymywać skradziony token przy życiu w nieskończoność jednym żądaniem co kilka godzin, czyli znosi korzyść z krótkiego czasu życia dokładnie w tym scenariuszu, przed którym się bronimy. Sufit absolutny łagodzi to, ale nie usuwa, a dokłada maszynerii po obu stronach.
- **Paginacja osobno, po auth.** Odrzucona, bo `SubmissionList.tsx` i tak jest przepisywany pod logowanie — rozbicie oznaczałoby drugie przejście przez ten sam plik i drugie review.

## Changelog

- 2026-09-11 — utworzono spec
- 2026-09-11 — dodano model zagrożenia (atakujący = uczestnik hackathonu); sesja przesuwana z sufitem absolutnym zamiast stałego czasu życia; limit prób logowania wciągnięty do zakresu; pinowanie algorytmu JWT, stały czas odpowiedzi i ochrona przed enumeracją kont; wymóg siły hasła w skrypcie; CSP i zakaz `dangerouslySetInnerHTML`
- 2026-09-11 — limit bezczynności skrócony z 24 h do 8 h (decyzja: krótsze okno dla skradzionego tokena, bez kosztu dla pracującego organizatora)
- 2026-09-11 — status: Zaakceptowany, spec idzie do rozbicia na issues
- 2026-09-11 — rezygnacja z sesji przesuwanej na rzecz stałego, 8-godzinnego czasu życia tokena (decyzja: skradziony token nie może dać się przedłużać; efekt uboczny — prostsza konstrukcja, bez sufitu absolutnego i nagłówka odnawiającego)
- 2026-09-11 — dodano ostrzeżenie z odliczaniem na 10 minut przed wygaśnięciem sesji (bez automatycznego przedłużania — przycisk prowadzi do logowania)
