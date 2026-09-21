FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app

# Alembic w obrazie jest WYMAGANY w czasie dzialania: sprawdzanie gotowosci
# (/health/ready, #91) czyta z tego katalogu, ktorych migracji oczekuje kod,
# i bez niego backend w ogole nie wstanie. Przy okazji pozwala migrowac baze
# z dzialajacego kontenera: docker compose exec backend alembic upgrade head
COPY backend/alembic.ini .
COPY backend/alembic ./alembic

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
