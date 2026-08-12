from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_hello() -> None:
    response = client.get("/api/hello")
    assert response.status_code == 200
    assert "message" in response.json()


def test_db_check() -> None:
    response = client.get("/api/db-check")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
