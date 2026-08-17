Katalog na migracje. Jest pusty — pierwsza migracja powstanie razem z modelem
zgłoszenia uczestnika. Plik istnieje po to, żeby git zapamiętał sam katalog:
bez niego `alembic upgrade head` przerywa błędem „Path doesn't exist".
