"""Smoke tests for the FastAPI skeleton."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_root():
    # Serves the built SPA when present, otherwise a JSON service descriptor.
    resp = client.get("/")
    assert resp.status_code == 200
    if resp.headers["content-type"].startswith("application/json"):
        assert resp.json()["service"] == "ai-github-reviewer"
    else:
        assert 'id="root"' in resp.text
