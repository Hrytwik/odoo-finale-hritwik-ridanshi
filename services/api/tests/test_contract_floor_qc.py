import pytest


@pytest.mark.parametrize("role,path", [
    ("supervisor", "/api/floor"), ("qc", "/api/qc/queue"),
    ("qc", "/api/qc/model-card"), ("owner", "/api/rolls/R-0142/passport"), ("buyer", "/api/rolls/R-0142/passport"),
])
def test_example_data_served(client, login_as, role, path):
    login_as(role)
    assert client.get(path).status_code == 200


def test_floor_counts_match_cards(client, login_as):
    login_as("supervisor")
    board = client.get("/api/floor").json()
    statuses = [m["status"] for m in board["machines"]]
    assert board["running"] == statuses.count("running") and board["down"] == statuses.count("down")


def test_roll_off_needs_positive_metres(client, login_as):
    login_as("supervisor")
    assert client.post("/api/runs/45/rolls", json={"metres": 0}).status_code == 422
    assert client.post("/api/runs/45/rolls", json={"metres": 110}).status_code == 201


def test_load_rolls_needs_at_least_one(client, login_as):
    login_as("supervisor")
    assert client.post("/api/runs/46/load-rolls", json={"roll_codes": []}).status_code == 422


def test_inspection_defect_count_bounds(client, login_as):
    login_as("qc")
    body = {"roll_code": "R-0142", "verdict": "rework", "defects": [{"defect_type": "hole", "count": 0}]}
    assert client.post("/api/qc/inspections", json=body).status_code == 422


def test_box_coordinates_are_fractions(client, login_as):
    login_as("qc")
    body = {"roll_code": "R-0142", "verdict": "pass", "defects": [], "ai_suggestion": {
        "model_version": "v1", "verdict": "pass",
        "boxes": [{"x": 1.5, "y": 0, "w": 0.1, "h": 0.1, "defect_type": "hole", "confidence": 0.9}]}}
    assert client.post("/api/qc/inspections", json=body).status_code == 422


def test_qc_cannot_run_floor_actions(client, login_as):
    login_as("qc")
    assert client.post("/api/machines/LOOM-04/breakdown", json={"reason": "belt"}).status_code == 403
