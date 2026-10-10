from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import AppError, install_error_handlers
from app.core.schemas import NonBlank, PositiveQty


def make_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    class Body(BaseModel):
        name: NonBlank
        qty: PositiveQty

    @app.post("/thing")
    def thing(body: Body):
        return {"ok": True, "name": body.name}

    @app.get("/boom")
    def boom():
        raise AppError("ROLL_NOT_PASSED", "Roll R-0142 has not passed QC", field="roll_code")

    @app.get("/missing")
    def missing():
        raise AppError("NOT_FOUND", "Order not found", status=404)

    return app


client = TestClient(make_app())


def test_app_error_has_standard_shape():
    r = client.get("/boom")
    assert r.status_code == 409
    assert r.json() == {
        "code": "ROLL_NOT_PASSED",
        "message": "Roll R-0142 has not passed QC",
        "field": "roll_code",
        "fields": None,
    }


def test_app_error_custom_status():
    assert client.get("/missing").status_code == 404


def test_whitespace_only_text_is_rejected_with_field_name():
    r = client.post("/thing", json={"name": "   ", "qty": 5})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["field"] == "name"
    assert "name" in body["fields"]


def test_every_invalid_field_is_reported():
    r = client.post("/thing", json={"name": "", "qty": 0})
    assert set(r.json()["fields"]) == {"name", "qty"}


def test_text_is_trimmed():
    r = client.post("/thing", json={"name": "  Ravi  ", "qty": 1})
    assert r.status_code == 200
    assert r.json()["name"] == "Ravi"
