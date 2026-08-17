# Migracje bazy danych (Alembic)

Struktura bazy zmienia się razem z modelami w `app/`. Alembic prowadzi ponumerowany
dziennik tych zmian, żeby każda baza — lokalna u każdej osoby z zespołu i ta na
produkcji — dostała je w tej samej kolejności.

Wszystkie komendy uruchamiaj z katalogu `backend/`.

## Codzienne użycie

Doprowadź bazę do stanu zgodnego z kodem (po `git pull` z nowym modelem):

```bash
alembic upgrade head
```

Wygeneruj migrację po zmianie modeli — Alembic porówna kod z bazą i napisze różnicę:

```bash
alembic revision --autogenerate -m "dodaj tabele submissions"
```

**Wygenerowany plik zawsze przejrzyj przed zacommitowaniem.** Autogenerate dobrze
wykrywa nowe tabele i kolumny, ale zmiany typów czy zmiany nazw potrafi zinterpretować
jako usunięcie i dodanie od nowa — czyli utratę danych.

Sprawdź, na której migracji stoi baza:

```bash
alembic current
```

Cofnij ostatnią migrację:

```bash
alembic downgrade -1
```

## W Dockerze

Kontener backendu ma komplet plików Alembica, więc:

```bash
docker compose exec backend alembic upgrade head
```

Migracje **nie uruchamiają się automatycznie** przy `docker compose up` — to świadoma
decyzja. Po pobraniu zmian z nowym modelem trzeba odpalić `upgrade head` samodzielnie.

## Jak to jest skonfigurowane

`env.py` bierze adres bazy z `DATABASE_URL` przez `app.db` — ten sam, którego używa
aplikacja. W `alembic.ini` nie ma i nie może być poświadczeń; `gitleaks` w CI pilnuje
tego przy każdym pull requeście.

Silnik jest asynchroniczny (asyncpg), dlatego `env.py` korzysta z wariantu async
(`async_engine_from_config` + `run_sync`), a nie z domyślnego szablonu Alembica.

Katalog `versions/` jest na razie pusty — pierwsza migracja powstanie razem z modelem
zgłoszenia uczestnika.
