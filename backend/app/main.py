from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import validation_exception_handler
from app.routers import submissions

app = FastAPI(title="hackathon-matching API")

app.include_router(submissions.router)

# Domyślne komunikaty walidacji pydantica są po angielsku, a front pokazuje je
# uczestnikowi wprost - stąd własny handler (patrz app/errors.py).
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "hackathon-matching API"}


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello World z backendu hackathon-matching!"}


@app.get("/api/db-check")
async def db_check(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    """Przykład komunikacji z Postgresem - sprawdza czy polaczenie dziala."""
    result = await session.execute(text("SELECT 1"))
    result.scalar_one()
    return {"status": "ok", "database": "connected"}
