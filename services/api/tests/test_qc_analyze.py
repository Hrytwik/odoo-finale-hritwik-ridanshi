"""B8 Task 2: POST /qc/analyze with a fake detector standing in for the model."""
import json
import threading
import time

import pytest

from app.config import settings
from app.modules.qc import vision

NAME = "ab12" * 8 + ".jpg"
PHOTO = "uploads/" + NAME
HOLE = ("hole", (0.2, 0.3, 0.6, 0.7), 0.9)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(vision, "_detector", None)
    monkeypatch.setattr(vision, "CARD_PATH", tmp_path / "no_card.json")
    (tmp_path / NAME).write_bytes(b"\xff\xd8\xff fake")


def fake(monkeypatch, detections):
    monkeypatch.setattr(vision, "_detector", lambda path: list(detections))


def analyze(client, path=PHOTO):
    return client.post("/api/qc/analyze", json={"photo_path": path})


def test_requires_login(client):
    assert analyze(client).status_code == 401


@pytest.mark.parametrize("role,status", [("qc", 200), ("owner", 200), ("dispatch", 403), ("supervisor", 403), ("buyer", 403)])
def test_roles(client, login_as, monkeypatch, role, status):
    fake(monkeypatch, [])
    login_as(role)
    assert analyze(client).status_code == status


def test_a_hole_becomes_a_box_and_a_rework_suggestion(client, login_as, monkeypatch):
    fake(monkeypatch, [HOLE])
    login_as("qc")
    body = analyze(client).json()
    assert body["available"] is False                      # no card shows the bar met: the suggestion is flagged unvalidated
    assert "Unvalidated" in body["message"] and "does not mean" in body["message"]
    s = body["suggestion"]
    assert s["verdict"] == "rework" and s["model_version"] == "best"
    assert s["boxes"] == [{"x": 0.2, "y": 0.3, "w": pytest.approx(0.4), "h": pytest.approx(0.4),
                           "defect_type": "hole", "confidence": 0.9}]


def test_nothing_found_suggests_pass_with_the_same_warning(client, login_as, monkeypatch):
    fake(monkeypatch, [])
    login_as("qc")
    body = analyze(client).json()
    assert body["suggestion"]["verdict"] == "pass" and body["suggestion"]["boxes"] == []
    assert "does not mean" in body["message"]


def test_a_guess_below_the_confidence_line_is_ignored_and_exactly_on_it_is_kept(client, login_as, monkeypatch):
    fake(monkeypatch, [("hole", (0.1, 0.1, 0.2, 0.2), 0.24), ("stain", (0.5, 0.5, 0.6, 0.6), 0.25)])
    login_as("qc")
    boxes = analyze(client).json()["suggestion"]["boxes"]
    assert [b["defect_type"] for b in boxes] == ["stain"]


def test_at_most_100_boxes(client, login_as, monkeypatch):
    fake(monkeypatch, [("hole", (0.1, 0.1, 0.2, 0.2), 0.3 + i / 1000) for i in range(150)])
    login_as("qc")
    assert len(analyze(client).json()["suggestion"]["boxes"]) == 100


def test_the_model_version_comes_from_the_card_file(client, login_as, monkeypatch, tmp_path):
    fake(monkeypatch, [])
    (tmp_path / "card.json").write_text('{"model_version": "yolo-test-1"}')
    monkeypatch.setattr(vision, "CARD_PATH", tmp_path / "card.json")
    login_as("qc")
    assert analyze(client).json()["suggestion"]["model_version"] == "yolo-test-1"


@pytest.mark.parametrize("path", ["../etc/passwd", "http://example.com/a.jpg", "uploads/../x.jpg", "uploads/" + "g" * 32 + ".jpg",
                                  "uploads/" + "ab12" * 8 + ".gif", ""])
def test_a_path_that_is_not_an_upload_is_refused(client, login_as, monkeypatch, path):
    fake(monkeypatch, [])
    login_as("qc")
    assert analyze(client, path).status_code == 422


def test_an_upload_path_with_no_file_behind_it_is_404(client, login_as, monkeypatch):
    fake(monkeypatch, [])
    login_as("qc")
    assert analyze(client, "uploads/" + "cd34" * 8 + ".jpg").status_code == 404


def test_an_unreadable_photo_is_422_with_a_plain_message(client, login_as, monkeypatch):
    def unreadable(path):
        raise vision.PhotoUnreadable()
    monkeypatch.setattr(vision, "_detector", unreadable)
    login_as("qc")
    r = analyze(client)
    assert r.status_code == 422 and r.json()["field"] == "photo_path" and "read this photo" in r.json()["message"].lower()


def test_the_model_failing_on_a_photo_is_not_a_500(client, login_as, monkeypatch):
    def broken(path):
        raise RuntimeError("out of memory")
    monkeypatch.setattr(vision, "_detector", broken)
    login_as("qc")
    r = analyze(client)
    assert r.status_code == 200 and r.json()["available"] is False and r.json()["suggestion"] is None
    assert "by hand" in r.json()["message"]


def test_missing_weights_give_available_false_with_the_reason(client, login_as, monkeypatch, tmp_path):
    monkeypatch.setattr(vision, "WEIGHTS_PATH", tmp_path / "nope.pt")
    login_as("qc")
    r = analyze(client)
    assert r.status_code == 200
    assert r.json()["available"] is False and r.json()["suggestion"] is None and "missing" in r.json()["message"]


def test_corrupt_weights_give_available_false(client, login_as, monkeypatch, tmp_path):
    pytest.importorskip("ultralytics")
    (tmp_path / "bad.pt").write_bytes(b"not a model")
    monkeypatch.setattr(vision, "WEIGHTS_PATH", tmp_path / "bad.pt")
    login_as("qc")
    r = analyze(client)
    assert r.status_code == 200 and r.json()["available"] is False and "could not be loaded" in r.json()["message"]


def test_a_load_failure_is_not_remembered_so_fixing_it_works_on_the_next_request(client, login_as, monkeypatch):
    def cannot_load():
        raise vision.ModelUnavailable("The vision libraries are not installed.")
    monkeypatch.setattr(vision, "_load_detector", cannot_load)
    login_as("qc")
    assert analyze(client).json()["available"] is False
    monkeypatch.setattr(vision, "_load_detector", lambda: (lambda path: [HOLE]))
    fixed = analyze(client).json()
    assert [b["defect_type"] for b in fixed["suggestion"]["boxes"]] == ["hole"]


def test_the_model_is_loaded_once(client, login_as, monkeypatch):
    loads = []
    monkeypatch.setattr(vision, "_load_detector", lambda: loads.append(1) or (lambda path: []))
    login_as("qc")
    analyze(client)
    analyze(client)
    analyze(client)
    assert len(loads) == 1


def test_two_photos_at_once_never_run_the_model_at_the_same_time(monkeypatch):
    running, peak = [0], [0]

    def slow(path):
        running[0] += 1
        peak[0] = max(peak[0], running[0])
        time.sleep(0.05)
        running[0] -= 1
        return []
    monkeypatch.setattr(vision, "_detector", slow)
    threads = [threading.Thread(target=vision.analyze_photo, args=(PHOTO,)) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert peak[0] == 1


def write_card(tmp_path, monkeypatch, **changes):
    card = {
        "model_version": "yolo-validated", "trained_at": "2026-10-10T09:30:00+00:00", "datasets": [],
        "test_defective": 40, "test_clean": 35, "clean_false_alarm_rate": 0.1,
        "per_class": [{"defect_type": "hole", "found": 34, "missed": 6, "false_alarms": 4, "precision": 0.89, "recall": 0.85}],
        "confusion_labels": ["hole", "clean"], "confusion_matrix": [[34, 6], [4, 0]],
    }
    card.update(changes)
    path = tmp_path / "validated_card.json"
    path.write_text(json.dumps(card))
    monkeypatch.setattr(vision, "CARD_PATH", path)


def test_a_model_whose_card_clears_the_bar_is_available_with_no_unvalidated_label(client, login_as, monkeypatch, tmp_path):
    fake(monkeypatch, [HOLE])
    write_card(tmp_path, monkeypatch)
    login_as("qc")
    body = analyze(client).json()
    assert body["available"] is True and body["message"] is None
    assert body["suggestion"]["model_version"] == "yolo-validated" and body["suggestion"]["verdict"] == "rework"


def test_a_card_that_misses_the_bar_keeps_the_unvalidated_label(client, login_as, monkeypatch, tmp_path):
    fake(monkeypatch, [HOLE])
    write_card(tmp_path, monkeypatch, clean_false_alarm_rate=0.3)
    login_as("qc")
    body = analyze(client).json()
    assert body["available"] is False and "Unvalidated" in body["message"] and body["suggestion"] is not None


def card(**changes):
    base = {
        "available": True, "model_version": "v", "trained_at": None, "datasets": [], "test_defective": 40, "test_clean": 35,
        "clean_false_alarm_rate": 0.1, "confusion_labels": [], "confusion_matrix": [],
        "per_class": [{"defect_type": "hole", "found": 34, "missed": 6, "false_alarms": 0, "precision": 1.0, "recall": 0.85}],
    }
    base.update(changes)
    return vision.s.ModelCard(**base)


def holes(found, missed):
    return [{"defect_type": "hole", "found": found, "missed": missed, "false_alarms": 0, "precision": None, "recall": None}]


@pytest.mark.parametrize("changes,expected", [
    ({}, True),
    ({"available": False}, False),                                        # no card at all
    ({"clean_false_alarm_rate": None}, False),                            # never measured
    ({"test_clean": 29}, False), ({"test_clean": 30}, True),             # needs 30 clean test photos
    ({"test_defective": 29}, False), ({"test_defective": 30}, True),     # and 30 defective ones
    ({"per_class": holes(24, 6)}, True),                                  # exactly 80% of holes found
    ({"per_class": holes(79, 21)}, False),                                # 79%
    ({"per_class": holes(0, 0)}, False),                                  # no holes in the test
    ({"per_class": []}, False),                                           # no hole row at all
    ({"clean_false_alarm_rate": 0.2}, True), ({"clean_false_alarm_rate": 0.21}, False),
    ({"clean_false_alarm_rate": 7 / 35}, True),                           # 7 of 35 is exactly 20%
])
def test_the_bar_is_the_spec_kill_criteria(changes, expected):
    assert vision._validated(card(**changes)) is expected
