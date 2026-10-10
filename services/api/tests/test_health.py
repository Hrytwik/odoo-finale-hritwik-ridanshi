from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_ok_and_demo_flag():
    with TestClient(app) as c:
        r = c.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["demo_data"], bool)
