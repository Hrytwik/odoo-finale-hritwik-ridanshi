"""B8 Task 5: GET /qc/model-card serves the saved card, and degrades to 'not evaluated yet' when it cannot."""
import json

import pytest

from app.modules.qc import vision
from app.modules.qc.schemas import ModelCard


def committed():
    return json.loads(vision.CARD_PATH.read_text())


def test_the_committed_card_passes_the_api_schema():
    ModelCard(available=True, **committed())


def test_the_committed_card_adds_up():
    card = committed()
    labels, matrix = card["confusion_labels"], card["confusion_matrix"]
    assert labels[-1] == "clean" and len(matrix) == len(labels) and all(len(r) == len(labels) for r in matrix)
    for i, p in enumerate(card["per_class"]):
        assert labels[i] == p["defect_type"]
        assert matrix[i][i] == p["found"]
        assert sum(matrix[i]) == p["found"] + p["missed"]
        assert sum(row[i] for row in matrix) == p["found"] + p["false_alarms"]
    assert (card["clean_false_alarm_rate"] is None) == (card["test_clean"] == 0)       # never a made-up rate


def test_the_route_serves_the_committed_card(client, login_as):
    login_as("qc")
    body = client.get("/api/qc/model-card").json()
    assert body["available"] is True and body["model_version"] and body["datasets"]
    assert body["confusion_matrix"] == committed()["confusion_matrix"]


@pytest.mark.parametrize("role,status", [("qc", 200), ("owner", 200), ("supervisor", 200), ("accountant", 403), ("buyer", 403)])
def test_roles(client, login_as, role, status):
    login_as(role)
    assert client.get("/api/qc/model-card").status_code == status


def test_requires_login(client):
    assert client.get("/api/qc/model-card").status_code == 401


@pytest.mark.parametrize("content", [None, "", "not json", "[1, 2]", '{"model_version": "x"}'])
def test_a_missing_or_broken_card_is_not_evaluated_yet_not_an_error(client, login_as, monkeypatch, tmp_path, content):
    path = tmp_path / "card.json"
    if content is not None:
        path.write_text(content)
    monkeypatch.setattr(vision, "CARD_PATH", path)
    login_as("qc")
    r = client.get("/api/qc/model-card")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False and body["per_class"] == [] and body["confusion_matrix"] == []
