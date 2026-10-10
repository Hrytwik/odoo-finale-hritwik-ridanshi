# B8 — Vision Endpoint and Model Card Implementation Plan

> **Summary:** Makes `POST /qc/analyze` run the fine-tuned YOLO detector on an uploaded photo (boxes with confidence, a suggested verdict, always labelled unvalidated) and `GET /qc/model-card` serve the measured held-out results with a confusion matrix; adds the committed weights and card file, makes the model-card screen show an unmeasured false-alarm rate honestly, and ends with a live check on a real server.
> **Last updated:** 2026-10-11 02:10 IST (Tasks 1-4 done)

> **How this plan is executed:** inline, one task at a time (atomic-workflow): test first, the full suite twice at each boundary, the important behaviours mutation-checked. Steps use checkbox (`- [ ]`) syntax.

**Goal:** a QC inspector photographs a roll and sees the model's boxes and a suggested verdict (which they confirm or override); the owner and QC see a model card with only measured numbers, including that false alarms on clean cloth were not measured.

**Architecture:** one new module `app/modules/qc/vision.py` holds everything about the model: the pure parts (corner boxes to contract boxes, the verdict rule), a lazy loader for the Ultralytics detector with a lock and an "unavailable" path, a photo reader that applies the phone's rotation, and the reader of the saved model-card file. The routes stay thin. The card file is produced once, offline, by `ml/model_card.py` (built on the existing `ml.metrics` matching, which gains a confusion matrix), and committed next to the weights.

**Tech Stack:** Python 3.12, FastAPI, pytest (`uv run python -m pytest -p no:warnings -o addopts=` from `services/api`), Ultralytics YOLO (optional `ml` dependency group), Pillow, React + vitest for the one screen edit. No new dependencies.

**Spec:** `docs/specs/2026-10-11-vision-endpoint-design.md` (read it first), parent `docs/specs/2026-10-10-textile-mill-design.md` §9. Background numbers: `docs/plans/BV-vision-spike.md`.

## Status

Task 1 done and verified (2026-10-11 01:55 IST): `qc/vision.py` (box conversion, verdict rule) and 16 tests; all six planned mutations (swap x/y, width from the right edge, area check `<`, no corner sort, `reject`, no cap) make a test fail; full backend suite 1,368 passed (1,352 before), twice.

Task 2 done and verified (2026-10-11 02:02 IST): `qc/vision.py` (photo reading, lazy loader with lock, `analyze_photo`), the real `/qc/analyze` route, the example `ANALYZE` removed, 37 tests (`test_qc_photo_reading.py`, `test_qc_analyze.py`); full backend suite 1,405 passed (1,368 before), twice; contract byte-identical. **A real bug found by the tests' ordering and fixed:** once Ultralytics is loaded it replaces `PIL.Image.open` with a wrapper that, on ANY failure, runs `pip install pi-heif` (a network call mid-request, retried) and then raises `ModuleNotFoundError`; a corrupt photo would have stalled and come back as "model failed" instead of a 422. The reader now calls PIL's own original (`_pil_open`); the new regression test `test_a_bad_photo_never_makes_ultralytics_try_to_install_a_package` failed against the old code first (and the photo tests now import Ultralytics up front, so they run in production's state in any order). One planned mutation (cache a failed load) first survived because the test only checked `available`; the test now checks the fixed detector's box comes back, and the mutation dies. No server was listening on :8000, so nothing to re-check.

Task 3 done and verified (2026-10-11 02:06 IST): `ml/metrics.py` gains `ImageMatch`, `match_image` (the old matching, shared) and `confusion_matrix`; `evaluate` now uses the shared matching and every existing metric test stayed green; 11 new tests (cells, wrong-name = miss + false alarm, one defect found once, unknown class is an error, and rows/columns equal the per-class scores on 300 random photos, checked non-empty); four mutations all die; full backend suite 1,416 passed (1,405 before), twice.

Task 4 done and verified (2026-10-11 02:10 IST): `ml/model_card.py` and 6 tests; ran it: `ml/models/best.pt` (5,466,629 bytes, byte-identical to the trained run) and `ml/models/model_card.json` committed; the card's per-class numbers equal the saved evaluation report exactly (hole 24/2/4, stain 18/11/4, thread fault 8/24/4; 59 defective, 0 clean, false-alarm rate null) and the matrix rows sum to 26, 29 and 32; git accepts both files; full backend suite 1,422 passed (1,416 before), twice.

## Global Constraints

- The contract types `AnalyzeIn`, `AnalyzeOut`, `AiSuggestion`, `Box`, `ModelCard` do not change; `contracts/openapi.json` and `contracts/types.ts` stay byte-identical (`test_committed_contract_matches_the_code` proves it).
- Box position fields `x`, `y` are the box's **top-left corner**, `w`, `h` its size, all 0–1 fractions of the photo.
- Detector settings: image size 640, confidence **0.25** (predict at 0.05, keep boxes at 0.25 or more, exactly as `ml.evaluate` and `ml.show_examples` do), matching overlap **0.3**.
- Verdict rule: no boxes → `pass`; one or more → `rework`; **never `reject`**.
- At most 100 boxes, highest confidence first.
- Roles unchanged: `/qc/analyze` for `qc`, `owner`; `/qc/model-card` for `qc`, `owner`, `supervisor`.
- `photo_path` must pass `check_upload_path` (an upload the app handed out).
- QC works without the model: any model problem gives HTTP 200 with `available=false` and a plain reason, never a 500. A photo that cannot be read gives 422.
- Real numbers only on the model card; the clean-cloth false-alarm rate is `null` (not measured) because the test set has no clean photos.
- Commit locally, never push.
- Hritwik's dev server auto-reloads from this folder: after each task that changes `app/`, if `lsof -nP -iTCP:8000 -sTCP:LISTEN` shows it, confirm `GET /api/health` still answers. This plan has no migrations.

## Review Focus

The inputs and conditions the spec implies but does not spell out, most likely first, each pinned by a test in the task that owns the code:

1. **A phone photo stored sideways** (EXIF rotation tag): the browser shows it upright, so the boxes must be computed on the upright picture. Pinned in Task 2 (`_read_upright`) and Task 6 (live, with a real rotated copy).
2. **A degenerate or out-of-frame box** (zero area, swapped corners, partly or wholly outside the photo): clamped, or dropped if no area is left. Task 1.
3. **A file that passed the upload header check but is not a readable image**, or a decompression bomb: 422, not a crash. Task 2.
4. **Two inspectors analysing at the same moment**: calls are serialised by one lock. Task 2.
5. **Model trouble at any stage** (weights missing, libraries not installed, weights corrupt, class names the contract does not know, the model failing on a photo, the card file missing or corrupt or in the wrong shape): HTTP 200, `available=false`, never a 500, and a fixed failure is not cached. Tasks 2 and 5.
6. **An unmeasured rate shown as 0%**: the model-card screen must say "Not measured", not "0%", and must not say "below the bar" when nothing was measured. Task 5.

---

## File structure

| File | Responsibility |
|---|---|
| `services/api/app/modules/qc/vision.py` (create) | everything about the model: box conversion, verdict rule, photo reading, lazy loader with lock, `analyze_photo`, `read_card` |
| `services/api/app/modules/qc/router.py` (modify) | `/qc/analyze` and `/qc/model-card` call `vision` |
| `services/api/app/modules/qc/examples.py` (modify) | remove the now-unused `ANALYZE` and `MODEL_CARD` example data |
| `services/api/ml/metrics.py` (modify) | one shared matching helper; `confusion_matrix` |
| `services/api/ml/model_card.py` (create) | builds `ml/models/model_card.json` and copies the weights to `ml/models/best.pt` |
| `services/api/ml/models/best.pt`, `model_card.json` (create, committed) | the shipped model and its card (`.gitignore` already allows `ml/models/*.pt`) |
| `apps/web/src/pages/qc/ModelCard.tsx` and `.test.tsx` (modify) | show an unmeasured false-alarm rate honestly |
| `package.json` (modify) | `dev:api` starts with `--group ml` so a fresh clone has the vision libraries |
| tests | `test_qc_vision_boxes.py`, `test_qc_photo_reading.py`, `test_qc_analyze.py`, `test_ml_confusion.py`, `test_ml_model_card.py`, `test_qc_model_card.py` (all in `services/api/tests/`) |

---

### Task 1: Box conversion and the verdict rule

**Files:**
- Create: `services/api/app/modules/qc/vision.py` (the pure part only)
- Test: `services/api/tests/test_qc_vision_boxes.py`

**Interfaces:**
- Produces: `Detection = tuple[str, tuple[float, float, float, float], float]` (defect type, corners left/top/right/bottom as 0–1 fractions, confidence); `MAX_BOXES = 100`; `to_boxes(detections: list[Detection]) -> list[schemas.Box]`; `suggest_verdict(boxes: list[schemas.Box]) -> Verdict`.

- [x] **Step 1: Write the failing tests**

`services/api/tests/test_qc_vision_boxes.py`:

```python
"""B8 Task 1: the detector's corner boxes become the contract's top-left-plus-size boxes; the verdict rule."""
from itertools import product

import pytest

from app.modules.qc.vision import MAX_BOXES, suggest_verdict, to_boxes


def det(cls="hole", corners=(0.2, 0.3, 0.6, 0.7), conf=0.9):
    return (cls, corners, conf)


def test_corners_become_top_left_plus_size():
    [b] = to_boxes([det(corners=(0.2, 0.3, 0.6, 0.7))])
    assert (b.x, b.y) == (0.2, 0.3)
    assert b.w == pytest.approx(0.4) and b.h == pytest.approx(0.4)
    assert b.defect_type == "hole" and b.confidence == 0.9


def test_a_box_that_is_not_square_keeps_width_and_height_apart():
    [b] = to_boxes([det(corners=(0.1, 0.2, 0.5, 0.3))])          # wide and short
    assert b.w == pytest.approx(0.4) and b.h == pytest.approx(0.1)


def test_the_whole_photo():
    [b] = to_boxes([det(corners=(0.0, 0.0, 1.0, 1.0))])
    assert (b.x, b.y, b.w, b.h) == (0.0, 0.0, 1.0, 1.0)


def test_a_box_touching_the_right_and_bottom_edges():
    [b] = to_boxes([det(corners=(0.9, 0.8, 1.0, 1.0))])
    assert b.x + b.w == pytest.approx(1.0) and b.y + b.h == pytest.approx(1.0)


def test_a_tiny_box_is_kept():
    [b] = to_boxes([det(corners=(0.5, 0.5, 0.501, 0.501))])
    assert 0 < b.w < 0.01 and 0 < b.h < 0.01


def test_swapped_corners_give_the_same_box():
    assert to_boxes([det(corners=(0.6, 0.7, 0.2, 0.3))]) == to_boxes([det(corners=(0.2, 0.3, 0.6, 0.7))])


def test_a_box_sticking_out_of_the_photo_is_clamped():
    [b] = to_boxes([det(corners=(-0.05, 0.2, 1.05, 0.5))])
    assert (b.x, b.w) == (0.0, 1.0)


@pytest.mark.parametrize("corners", [(1.0, 0.2, 1.0, 0.5), (0.2, 0.5, 0.6, 0.5), (1.2, 0.2, 1.5, 0.5), (-0.5, 0.2, -0.1, 0.5)])
def test_a_box_with_no_area_inside_the_photo_is_dropped(corners):
    assert to_boxes([det(corners=corners)]) == []


def test_every_combination_of_edge_values_stays_inside_the_photo():
    values = [-0.1, 0.0, 0.3, 0.5, 1.0, 1.1]
    for corners in product(values, repeat=4):
        for b in to_boxes([det(corners=corners)]):
            assert 0 <= b.x <= 1 and 0 <= b.y <= 1
            assert 0 < b.w <= 1 and 0 < b.h <= 1
            assert b.x + b.w <= 1 + 1e-9 and b.y + b.h <= 1 + 1e-9


def test_highest_confidence_first_and_at_most_100():
    detections = [det(conf=0.25 + i / 1000) for i in range(150)]
    boxes = to_boxes(detections)
    assert len(boxes) == MAX_BOXES == 100
    confidences = [b.confidence for b in boxes]
    assert confidences == sorted(confidences, reverse=True)
    assert confidences[0] == pytest.approx(0.25 + 149 / 1000) and confidences[-1] == pytest.approx(0.25 + 50 / 1000)


def test_dropped_degenerate_boxes_do_not_use_up_the_100():
    junk = [det(corners=(1.0, 0.2, 1.0, 0.5), conf=0.99) for _ in range(10)]
    real = [det(conf=0.5 + i / 1000) for i in range(100)]
    assert len(to_boxes(junk + real)) == 100


def test_no_detections_no_boxes():
    assert to_boxes([]) == []


def test_verdict_is_pass_without_boxes_and_rework_with_any_and_never_reject():
    assert suggest_verdict([]) == "pass"
    one = to_boxes([det()])
    assert suggest_verdict(one) == "rework"
    assert suggest_verdict(to_boxes([det(conf=0.25 + i / 1000) for i in range(100)])) == "rework"
```

- [x] **Step 2: Run to verify it fails.** `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_qc_vision_boxes.py` — Expected: collection error, `app.modules.qc.vision` does not exist.

- [x] **Step 3: Write the minimal implementation.** `services/api/app/modules/qc/vision.py`:

```python
"""Vision QC (B8): run the fine-tuned defect detector on one uploaded photo, and serve the saved model card.

The pure parts (box conversion, the verdict rule) are plain Python and unit-tested without the model.
"""
from app.core.enums import Verdict
from app.modules.qc import schemas as s

MAX_BOXES = 100                                        # the contract's limit on AiSuggestion.boxes
Corners = tuple[float, float, float, float]            # left, top, right, bottom, each a 0-1 fraction of the photo
Detection = tuple[str, Corners, float]                 # defect type, corners, confidence


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def to_boxes(detections: list[Detection]) -> list[s.Box]:
    """The detector gives corners; the contract (and the screen) want the top-left corner plus a size. Best confidence
    first; a box is clamped into the photo, and dropped if no area is left inside it."""
    boxes: list[s.Box] = []
    for defect_type, (a, b, c, d), confidence in sorted(detections, key=lambda det: det[2], reverse=True):
        left, right = sorted((_clamp(a), _clamp(c)))
        top, bottom = sorted((_clamp(b), _clamp(d)))
        if right <= left or bottom <= top:
            continue
        boxes.append(s.Box(x=left, y=top, w=right - left, h=bottom - top, defect_type=defect_type,
                           confidence=_clamp(confidence)))
        if len(boxes) == MAX_BOXES:
            break
    return boxes


def suggest_verdict(boxes: list[s.Box]) -> Verdict:
    """Anything found makes a person look (rework); nothing found is a pass. The model never suggests reject: scrapping a
    roll stays a human decision. The inspector confirms or overrides either way."""
    return "rework" if boxes else "pass"
```

- [x] **Step 4: Run it.** Same command. Expected: all pass.
- [x] **Step 5: Mutation checks** (apply each, see a test fail, undo): swap `x=left` and `y=top`; use `w=right` instead of `right - left`; change `<=` to `<` in the area check; drop the `sorted` of the corners; change `"rework"` to `"reject"`; remove the cap.
- [x] **Step 6: Full suite twice** (`uv run python -m pytest -p no:warnings -o addopts=`), both green. Expected count: previous total + the new tests (note the number).
- [x] **Step 7: Commit.**

```bash
git add services/api/app/modules/qc/vision.py services/api/tests/test_qc_vision_boxes.py
git commit -m "Add the vision box conversion and the suggested-verdict rule"
```

---

### Task 2: Reading the photo, loading the detector, and the real `/qc/analyze`

**Files:**
- Modify: `services/api/app/modules/qc/vision.py` (replace with the full file below)
- Modify: `services/api/app/modules/qc/router.py` (the `analyze` route)
- Modify: `services/api/app/modules/qc/examples.py` (remove `ANALYZE` and the `AnalyzeOut` import)
- Test: `services/api/tests/test_qc_photo_reading.py`, `services/api/tests/test_qc_analyze.py`

**Interfaces:**
- Consumes (Task 1): `to_boxes`, `suggest_verdict`, `Detection`, `MAX_BOXES`.
- Produces: `CONFIDENCE = 0.25`, `WEIGHTS_PATH`, `CARD_PATH` (module constants tests monkeypatch), `ModelUnavailable(reason)`, `PhotoUnreadable`, `_read_upright(path)`, `_check_class_names(names)`, `_load_detector() -> Callable[[Path], list[Detection]]`, module global `_detector`, `analyze_photo(photo_path: str) -> schemas.AnalyzeOut`.

- [x] **Step 1: Write the failing tests.**

`services/api/tests/test_qc_photo_reading.py` (needs only Pillow, no model):

```python
"""B8 Task 2: photos are read the way a browser shows them (rotation applied); unreadable files are refused cleanly."""
import pytest

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from app.modules.qc.vision import PhotoUnreadable, _check_class_names, ModelUnavailable, _read_upright  # noqa: E402


def save_jpeg(path, size=(40, 20), orientation=None):
    img = Image.new("RGB", size, "white")
    exif = img.getexif()
    if orientation is not None:
        exif[0x0112] = orientation
    img.save(path, "JPEG", exif=exif)
    return path


def test_a_normal_photo_keeps_its_size(tmp_path):
    assert _read_upright(save_jpeg(tmp_path / "a.jpg")).size == (40, 20)


@pytest.mark.parametrize("orientation,size", [(1, (40, 20)), (3, (40, 20)), (6, (20, 40)), (8, (20, 40))])
def test_the_phones_rotation_tag_is_applied(tmp_path, orientation, size):
    assert _read_upright(save_jpeg(tmp_path / "a.jpg", orientation=orientation)).size == size


def test_the_result_has_three_colour_channels(tmp_path):
    Image.new("L", (10, 10)).save(tmp_path / "g.png")
    assert _read_upright(tmp_path / "g.png").mode == "RGB"


def test_bytes_that_are_not_an_image_are_refused(tmp_path):
    (tmp_path / "x.jpg").write_bytes(b"\xff\xd8\xff this is not really a picture")
    with pytest.raises(PhotoUnreadable):
        _read_upright(tmp_path / "x.jpg")


def test_a_cut_off_file_is_refused(tmp_path):
    good = save_jpeg(tmp_path / "a.jpg", size=(200, 200)).read_bytes()
    (tmp_path / "cut.jpg").write_bytes(good[: len(good) // 2])
    with pytest.raises(PhotoUnreadable):
        _read_upright(tmp_path / "cut.jpg")


def test_a_decompression_bomb_is_refused(tmp_path, monkeypatch):
    save_jpeg(tmp_path / "big.jpg", size=(200, 200))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)           # 200 x 200 is far above twice this limit
    with pytest.raises(PhotoUnreadable):
        _read_upright(tmp_path / "big.jpg")


def test_class_names_the_contract_knows_are_accepted():
    _check_class_names({0: "hole", 1: "stain", 2: "thread_fault"})


def test_class_names_the_contract_does_not_know_make_the_model_unavailable():
    with pytest.raises(ModelUnavailable) as err:
        _check_class_names({0: "hole", 1: "banana"})
    assert "banana" in err.value.reason
```

`services/api/tests/test_qc_analyze.py`:

```python
"""B8 Task 2: POST /qc/analyze with a fake detector standing in for the model."""
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
    assert body["available"] is True
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
    assert analyze(client).json()["available"] is True


def test_the_model_is_loaded_once(client, login_as, monkeypatch):
    loads = []
    monkeypatch.setattr(vision, "_load_detector", lambda: loads.append(1) or (lambda path: []))
    login_as("qc")
    analyze(client); analyze(client); analyze(client)
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
```

- [x] **Step 2: Run to verify they fail.** `uv run python -m pytest -p no:warnings -o addopts= tests/test_qc_photo_reading.py tests/test_qc_analyze.py` — Expected: import errors (`PhotoUnreadable`, `_read_upright`, … not defined).

- [x] **Step 3: Replace `services/api/app/modules/qc/vision.py`** with the full file (it contains Task 1's code unchanged):

```python
"""Vision QC (B8): run the fine-tuned defect detector on one uploaded photo, and serve the saved model card.

The detector (Ultralytics YOLO) lives in the optional `ml` dependency group and is loaded lazily on the first photo. If it
cannot be loaded the endpoint answers `available=false` and quality checking carries on by hand (spec 9). Everything that
does not need the model (box conversion, the verdict rule, photo reading) is plain Python and unit-tested without it.
"""
import json
import logging
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import get_args

from app.core.enums import DefectType, Verdict
from app.core.validate import check_upload_path, invalid, not_found
from app.modules.qc import schemas as s
from app.modules.uploads.router import upload_root

logger = logging.getLogger(__name__)

MAX_BOXES = 100                                        # the contract's limit on AiSuggestion.boxes
Corners = tuple[float, float, float, float]            # left, top, right, bottom, each a 0-1 fraction of the photo
Detection = tuple[str, Corners, float]                 # defect type, corners, confidence

MODELS_DIR = Path(__file__).resolve().parents[3] / "ml" / "models"
WEIGHTS_PATH = MODELS_DIR / "best.pt"
CARD_PATH = MODELS_DIR / "model_card.json"
IMAGE_SIZE = 640
PREFILTER = 0.05                                       # predict this low, then keep CONFIDENCE and up: how ml.evaluate does it
CONFIDENCE = 0.25
NOTICE = ("Unvalidated first version, trained on public photos only. Nothing found does not mean the cloth is clean: "
          "thread faults and stains are often missed. The inspector decides. See the model card for the measured results.")
BY_HAND = "Inspect by hand."


class ModelUnavailable(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class PhotoUnreadable(Exception):
    pass


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def to_boxes(detections: list[Detection]) -> list[s.Box]:
    """The detector gives corners; the contract (and the screen) want the top-left corner plus a size. Best confidence
    first; a box is clamped into the photo, and dropped if no area is left inside it."""
    boxes: list[s.Box] = []
    for defect_type, (a, b, c, d), confidence in sorted(detections, key=lambda det: det[2], reverse=True):
        left, right = sorted((_clamp(a), _clamp(c)))
        top, bottom = sorted((_clamp(b), _clamp(d)))
        if right <= left or bottom <= top:
            continue
        boxes.append(s.Box(x=left, y=top, w=right - left, h=bottom - top, defect_type=defect_type,
                           confidence=_clamp(confidence)))
        if len(boxes) == MAX_BOXES:
            break
    return boxes


def suggest_verdict(boxes: list[s.Box]) -> Verdict:
    """Anything found makes a person look (rework); nothing found is a pass. The model never suggests reject: scrapping a
    roll stays a human decision. The inspector confirms or overrides either way."""
    return "rework" if boxes else "pass"


def _pil_open():
    """PIL's own Image.open. Once Ultralytics is loaded it replaces `Image.open` with a wrapper that, on ANY failure (a
    corrupt file, an oversized one), runs `pip install pi-heif` and then raises ModuleNotFoundError: a network call in the
    middle of a request (the demo may be offline) and the wrong error. We bypass the wrapper and use the original it saved."""
    from PIL import Image
    if Image.open.__module__ == "PIL.Image":
        return Image.open
    return sys.modules["ultralytics.utils.patches"]._image_open


def _read_upright(path: Path):
    """Open a photo the way a browser shows it: the phone's rotation tag applied, three colour channels. The boxes are
    worked out on this upright picture, so they land where the inspector sees the defect."""
    from PIL import Image, ImageOps
    try:
        with _pil_open()(path) as raw:
            return ImageOps.exif_transpose(raw).convert("RGB")
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise PhotoUnreadable() from exc


def _check_class_names(names: dict[int, str]) -> None:
    unknown = sorted(set(names.values()) - set(get_args(DefectType)))
    if unknown:
        raise ModelUnavailable(f"The model reports defect types this system does not know ({', '.join(unknown)}). {BY_HAND}")


def _load_detector() -> Callable[[Path], list[Detection]]:
    if not WEIGHTS_PATH.is_file():
        raise ModelUnavailable(f"The model file is missing (services/api/ml/models/best.pt), so there is no AI suggestion. {BY_HAND}")
    try:
        import torch
        from ultralytics import YOLO
    except ImportError:
        raise ModelUnavailable("The vision libraries are not installed (start the API with `uv run --group ml`), "
                               f"so there is no AI suggestion. {BY_HAND}") from None
    try:
        model = YOLO(str(WEIGHTS_PATH))
    except Exception:
        logger.exception("could not load the vision model from %s", WEIGHTS_PATH)
        raise ModelUnavailable(f"The model file could not be loaded, so there is no AI suggestion. {BY_HAND}") from None
    names = {int(k): v for k, v in model.names.items()}
    _check_class_names(names)
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    def detect(path: Path) -> list[Detection]:
        result = model.predict(_read_upright(path), imgsz=IMAGE_SIZE, conf=PREFILTER, device=device, verbose=False)[0]
        return [(names[int(c)], tuple(map(float, b)), float(p))
                for c, b, p in zip(result.boxes.cls, result.boxes.xyxyn, result.boxes.conf)]

    return detect


_lock = threading.Lock()
_detector: Callable[[Path], list[Detection]] | None = None


def _model_version() -> str:
    try:
        version = json.loads(CARD_PATH.read_text()).get("model_version")
    except (OSError, ValueError, AttributeError):
        version = None
    return version if isinstance(version, str) and version.strip() else WEIGHTS_PATH.stem


def analyze_photo(photo_path: str) -> s.AnalyzeOut:
    """One uploaded photo in, the model's boxes and suggested verdict out. Calls are serialised by one lock (whether the
    detector is safe to call from several threads at once is unverified, so it is not assumed)."""
    global _detector
    path = check_upload_path(photo_path, "photo_path")
    file = upload_root() / path.removeprefix("uploads/")
    if not file.is_file():
        raise not_found("Photo", "photo_path")
    try:
        with _lock:
            if _detector is None:
                _detector = _load_detector()          # a failure is not remembered: fixing the cause works next time
            detections = _detector(file)
    except ModelUnavailable as exc:
        return s.AnalyzeOut(available=False, message=exc.reason, suggestion=None)
    except PhotoUnreadable:
        raise invalid("Could not read this photo; take it again or upload a JPEG or PNG", "photo_path") from None
    except Exception:
        logger.exception("the vision model failed on %s", path)
        return s.AnalyzeOut(available=False, message=f"The model failed on this photo, so there is no AI suggestion. {BY_HAND}",
                            suggestion=None)
    boxes = to_boxes([d for d in detections if d[2] >= CONFIDENCE])
    return s.AnalyzeOut(available=True, message=NOTICE, suggestion=s.AiSuggestion(
        model_version=_model_version(), verdict=suggest_verdict(boxes), boxes=boxes))
```

- [x] **Step 4: Wire the route.** In `services/api/app/modules/qc/router.py` add `from app.modules.qc import vision` (next to the other `app.modules.qc` imports) and change the route body:

```python
@router.post("/qc/analyze", response_model=s.AnalyzeOut, dependencies=[Depends(inspectors)])
def analyze(body: s.AnalyzeIn) -> s.AnalyzeOut:
    return vision.analyze_photo(body.photo_path)
```

In `examples.py` delete the `ANALYZE = ...` line and `AnalyzeOut` from the import (it is used nowhere else; checked with `grep -rn "ANALYZE" app tests scripts ml`).

- [x] **Step 5: Run the new tests.** Expected: all pass (the `ultralytics`-dependent test runs here because Ultralytics 8.4.175 is installed; elsewhere it is skipped).
- [x] **Step 6: Mutation checks:** remove `ImageOps.exif_transpose` (the rotation test must fail); change `>= CONFIDENCE` to `> CONFIDENCE` (the exactly-0.25 test fails); remove the `with _lock:` (the concurrency test fails); cache the failed load by setting `_detector` before loading (the not-remembered test fails); remove the `except Exception` branch (the failing-model test fails).
- [x] **Step 7: Full suite twice;** both green; `test_committed_contract_matches_the_code` still passes (the contract is untouched).
- [x] **Step 8: Hritwik's server.** If `lsof -nP -iTCP:8000 -sTCP:LISTEN` shows it, `curl -s localhost:8000/api/health` still answers after the reload.
- [x] **Step 9: Commit.**

```bash
git add services/api/app/modules/qc services/api/tests/test_qc_photo_reading.py services/api/tests/test_qc_analyze.py
git commit -m "Make the photo analysis real: run the detector, with an honest unavailable path"
```

---

### Task 3: The confusion matrix, from the same matching the scores use

**Files:**
- Modify: `services/api/ml/metrics.py`
- Test: `services/api/tests/test_ml_confusion.py` (the existing `tests/test_ml_metrics.py` must stay green: it guards the refactor)

**Interfaces:**
- Produces: `ImageMatch(found, false_alarms, missed, kept_predictions)` dataclass; `match_image(img: ImageResult, iou_thr=0.3, conf_thr=0.25) -> ImageMatch`; `confusion_matrix(images: list[ImageResult], classes: list[str], iou_thr=0.3, conf_thr=0.25) -> list[list[int]]` of size `len(classes)+1` square; the last row and column mean "clean" (no defect). `evaluate` keeps its signature and results.

- [x] **Step 1: Write the failing tests.** `services/api/tests/test_ml_confusion.py`:

```python
"""B8 Task 3: the confusion matrix uses the very matching the per-class scores use, so the two always agree."""
import random

import pytest

from ml.metrics import ImageResult, confusion_matrix, evaluate

CLASSES = ["hole", "stain", "thread_fault"]
CLEAN = 3
BOX = (0.4, 0.4, 0.6, 0.6)
OFF = (0.0, 0.0, 0.1, 0.1)


def img(truths=(), preds=()):
    return ImageResult(truths=list(truths), preds=list(preds))


def test_a_found_defect_is_on_the_diagonal():
    m = confusion_matrix([img([("hole", BOX)], [("hole", BOX, 0.9)])], CLASSES)
    assert m[0][0] == 1 and sum(map(sum, m)) == 1


def test_a_missed_defect_is_in_the_clean_column_of_its_row():
    m = confusion_matrix([img([("stain", BOX)])], CLASSES)
    assert m[1][CLEAN] == 1 and sum(map(sum, m)) == 1


def test_a_false_alarm_is_in_the_clean_row_of_its_column():
    m = confusion_matrix([img(preds=[("hole", BOX, 0.9)])], CLASSES)
    assert m[CLEAN][0] == 1 and sum(map(sum, m)) == 1


def test_a_clean_photo_with_no_guess_is_the_clean_clean_cell():
    m = confusion_matrix([img()], CLASSES)
    assert m[CLEAN][CLEAN] == 1 and sum(map(sum, m)) == 1


def test_a_clean_photo_with_a_weak_guess_below_the_line_still_counts_as_clean():
    m = confusion_matrix([img(preds=[("hole", BOX, 0.2)])], CLASSES)
    assert m[CLEAN][CLEAN] == 1 and m[CLEAN][0] == 0


def test_a_defective_photo_with_no_guess_is_not_a_clean_clean_cell():
    m = confusion_matrix([img([("hole", BOX)])], CLASSES)
    assert m[CLEAN][CLEAN] == 0


def test_the_right_place_with_the_wrong_name_is_a_miss_plus_a_false_alarm():
    m = confusion_matrix([img([("hole", BOX)], [("stain", BOX, 0.9)])], CLASSES)
    assert m[0][CLEAN] == 1 and m[CLEAN][1] == 1 and m[0][1] == 0


def test_a_guess_far_from_the_defect_is_a_miss_plus_a_false_alarm():
    m = confusion_matrix([img([("hole", BOX)], [("hole", OFF, 0.9)])], CLASSES)
    assert m[0][CLEAN] == 1 and m[CLEAN][0] == 1


def test_one_real_defect_can_be_found_only_once():
    m = confusion_matrix([img([("hole", BOX)], [("hole", BOX, 0.9), ("hole", BOX, 0.8)])], CLASSES)
    assert m[0][0] == 1 and m[CLEAN][0] == 1


def test_an_unknown_class_is_an_error_not_a_silent_skip():
    with pytest.raises(ValueError, match="banana"):
        confusion_matrix([img([("banana", BOX)])], CLASSES)


def random_image(rng):
    def box():
        x, y = rng.random() * 0.7, rng.random() * 0.7
        return (x, y, x + 0.1 + rng.random() * 0.2, y + 0.1 + rng.random() * 0.2)
    truths = [(rng.choice(CLASSES), box()) for _ in range(rng.randint(0, 3))]
    preds = [(rng.choice(CLASSES), box(), rng.random()) for _ in range(rng.randint(0, 4))]
    preds += [(c, b, rng.random()) for c, b in truths if rng.random() < 0.6]             # some guesses sit on real defects
    return img(truths, preds)


def test_rows_and_columns_add_up_to_the_per_class_scores_on_random_photos():
    rng = random.Random(7)
    images = [random_image(rng) for _ in range(300)]
    ev = evaluate(images)
    m = confusion_matrix(images, CLASSES)
    for i, name in enumerate(CLASSES):
        score = ev.per_class.get(name)
        found, missed, false_alarms = (score.found, score.missed, score.false_alarms) if score else (0, 0, 0)
        assert m[i][i] == found
        assert sum(m[i]) == found + missed                      # row: everything really there
        assert sum(row[i] for row in m) == found + false_alarms  # column: everything the model said
    assert ev.defective_images + ev.clean_images == 300
    assert m[CLEAN][CLEAN] + ev.clean_alarm_images == ev.clean_images
```

- [x] **Step 2: Run to verify it fails.** `uv run python -m pytest -p no:warnings -o addopts= tests/test_ml_confusion.py` — Expected: `ImportError: cannot import name 'confusion_matrix'`.

- [x] **Step 3: Implement.** In `services/api/ml/metrics.py`, replace the body of `evaluate` by a shared helper (keep everything else in the file):

```python
@dataclass
class ImageMatch:
    found: list[str]            # the class of each real defect a guess found
    false_alarms: list[str]     # the class of each guess that found nothing
    missed: list[str]           # the class of each real defect no guess found
    kept_predictions: int       # guesses at or above the confidence line


def match_image(img: ImageResult, iou_thr: float = 0.3, conf_thr: float = 0.25) -> ImageMatch:
    """Greedy matching, highest confidence first; each real defect can be found once, and only by a guess of its own class."""
    preds = sorted((p for p in img.preds if p[2] >= conf_thr), key=lambda p: p[2], reverse=True)
    unmatched = list(img.truths)
    found: list[str] = []
    false_alarms: list[str] = []
    for cls, pbox, _ in preds:
        best, best_iou = None, 0.0
        for t in unmatched:
            score = iou(pbox, t[1]) if t[0] == cls else 0.0
            if score >= iou_thr and score > best_iou:
                best, best_iou = t, score
        if best is None:
            false_alarms.append(cls)
        else:
            unmatched.remove(best)
            found.append(cls)
    return ImageMatch(found, false_alarms, [cls for cls, _ in unmatched], len(preds))


def evaluate(images: list[ImageResult], iou_thr: float = 0.3, conf_thr: float = 0.25) -> Evaluation:
    out = Evaluation()
    for img in images:
        m = match_image(img, iou_thr, conf_thr)
        for cls in m.found:
            out.per_class.setdefault(cls, ClassResult()).found += 1
        for cls in m.false_alarms:
            out.per_class.setdefault(cls, ClassResult()).false_alarms += 1
        for cls in m.missed:
            out.per_class.setdefault(cls, ClassResult()).missed += 1
        if img.truths:
            out.defective_images += 1
        else:
            out.clean_images += 1
            if m.kept_predictions:
                out.clean_alarm_images += 1
    return out


def confusion_matrix(images: list[ImageResult], classes: list[str], iou_thr: float = 0.3, conf_thr: float = 0.25) -> list[list[int]]:
    """Rows: what was really there (each class, then 'clean' = nothing). Columns: what the model said (each class, then
    'clean' = nothing). Built from the same matching as `evaluate`, so a class's row adds up to its found + missed and its
    column to found + false alarms. A real defect that was missed sits in the 'clean' column of its row; a false alarm sits in
    the 'clean' row of its column; the clean-clean cell counts clean photos on which the model said nothing."""
    index = {name: i for i, name in enumerate(classes)}
    clean = len(classes)
    matrix = [[0] * (clean + 1) for _ in range(clean + 1)]

    def at(name: str) -> int:
        if name not in index:
            raise ValueError(f"class {name!r} is not one of {classes}")
        return index[name]

    for img in images:
        m = match_image(img, iou_thr, conf_thr)
        for cls in m.found:
            matrix[at(cls)][at(cls)] += 1
        for cls in m.missed:
            matrix[at(cls)][clean] += 1
        for cls in m.false_alarms:
            matrix[clean][at(cls)] += 1
        if not img.truths and not m.kept_predictions:
            matrix[clean][clean] += 1
    return matrix
```

- [x] **Step 4: Run** the new file and `tests/test_ml_metrics.py tests/test_ml_evaluate.py tests/test_ml_show_examples.py` — Expected: all pass (the refactor changed no result).
- [x] **Step 5: Mutation checks:** count a wrong-class guess as found; send misses to the row instead of the column; drop the `m.kept_predictions` test from the clean-clean cell; each must fail a test.
- [x] **Step 6: Full suite twice;** green.
- [x] **Step 7: Commit.**

```bash
git add services/api/ml/metrics.py services/api/tests/test_ml_confusion.py
git commit -m "Add a confusion matrix that uses the same matching as the detector scores"
```

---

### Task 4: Build and commit the model card and the weights

**Files:**
- Create: `services/api/ml/model_card.py`
- Create (by running it): `services/api/ml/models/best.pt`, `services/api/ml/models/model_card.json`
- Test: `services/api/tests/test_ml_model_card.py`

**Interfaces:**
- Consumes (Task 3): `confusion_matrix`; existing `ml.evaluate.score_directory`, `load_names`.
- Produces: `card_dict(ev, matrix, classes, *, model_version, trained_at, datasets) -> dict` whose keys are exactly the `ModelCard` fields except `available`; `DATASETS`; the committed files.

- [x] **Step 1: Write the failing tests.** `services/api/tests/test_ml_model_card.py`:

```python
"""B8 Task 4: the card file has exactly the shape the API serves."""
from datetime import UTC, datetime

from app.modules.qc.schemas import ModelCard
from ml.metrics import ImageResult, confusion_matrix, evaluate
from ml.model_card import DATASETS, card_dict

CLASSES = ["hole", "stain", "thread_fault"]
BOX = (0.4, 0.4, 0.6, 0.6)
WHEN = datetime(2026, 10, 10, 9, 30, tzinfo=UTC)


def build(images):
    return card_dict(evaluate(images), confusion_matrix(images, CLASSES), CLASSES,
                     model_version="yolo-test", trained_at=WHEN, datasets=DATASETS)


def images():
    return [ImageResult([("hole", BOX)], [("hole", BOX, 0.9)]), ImageResult([("stain", BOX)], [])]


def test_the_card_passes_the_api_schema():
    card = ModelCard(available=True, **build(images()))
    assert card.model_version == "yolo-test" and card.trained_at == WHEN
    assert (card.test_defective, card.test_clean) == (2, 0)


def test_every_class_is_listed_in_order_even_one_with_no_photos():
    card = build(images())
    assert [p["defect_type"] for p in card["per_class"]] == CLASSES
    thread = card["per_class"][2]
    assert (thread["found"], thread["missed"], thread["false_alarms"]) == (0, 0, 0)
    assert thread["precision"] is None and thread["recall"] is None


def test_with_no_clean_photos_the_false_alarm_rate_is_null_not_zero():
    assert build(images())["clean_false_alarm_rate"] is None


def test_with_clean_photos_it_is_the_measured_rate():
    imgs = images() + [ImageResult([], [("hole", BOX, 0.9)]), ImageResult([], [])]
    assert build(imgs)["clean_false_alarm_rate"] == 0.5


def test_the_matrix_labels_end_with_clean_and_the_matrix_is_square():
    card = build(images())
    assert card["confusion_labels"] == [*CLASSES, "clean"]
    assert all(len(row) == 4 for row in card["confusion_matrix"]) and len(card["confusion_matrix"]) == 4


def test_the_datasets_credit_the_roboflow_set_with_its_licence():
    [d] = DATASETS
    assert d["licence"] == "CC BY 4.0" and d["url"].startswith("https://universe.roboflow.com/")
```

- [x] **Step 2: Run to verify it fails** (`ModuleNotFoundError: ml.model_card`).

- [x] **Step 3: Write `services/api/ml/model_card.py`:**

```python
"""Build the model card the app serves: score the trained detector on the held-out photos, add the confusion matrix, and
save ml/models/model_card.json next to a copy of the weights (ml/models/best.pt).

Run (from services/api):  uv run --group ml python -m ml.model_card
The card has exactly the fields of the API's ModelCard (minus `available`), so the app reads it without translating.
Numbers are measured here, never typed: the test photos are the held-out public split (no clean photos, so the
clean-cloth false-alarm rate is null, not zero).
"""
import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from ml.evaluate import EvaluationError, load_names, score_directory
from ml.metrics import ClassResult, Evaluation, confusion_matrix

ML_DIR = Path(__file__).resolve().parent
CONFIDENCE = 0.25
OVERLAP = 0.3
CLEAN = "clean"
DATASETS = [{
    "name": "Fabric Defect Detection Subset (Roboflow Universe, First Workspace Gan)",
    "url": "https://universe.roboflow.com/first-workspace-gan/fabric-defect-detection-subset",
    "licence": "CC BY 4.0",
}]


def card_dict(ev: Evaluation, matrix: list[list[int]], classes: list[str], *, model_version: str,
              trained_at: datetime, datasets: list[dict]) -> dict:
    per_class = []
    for name in classes:
        r = ev.per_class.get(name, ClassResult())
        per_class.append({"defect_type": name, "found": r.found, "missed": r.missed, "false_alarms": r.false_alarms,
                          "precision": r.precision, "recall": r.recall})
    return {
        "model_version": model_version,
        "trained_at": trained_at.isoformat(timespec="seconds"),
        "datasets": datasets,
        "test_defective": ev.defective_images,
        "test_clean": ev.clean_images,
        "clean_false_alarm_rate": ev.clean_false_alarm_rate,
        "per_class": per_class,
        "confusion_labels": [*classes, CLEAN],
        "confusion_matrix": matrix,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", default=str(ML_DIR / "runs/public_only/weights/best.pt"))
    ap.add_argument("--data", default=str(ML_DIR / "data/public_only/data.yaml"), help="the dataset YAML (for the class names)")
    ap.add_argument("--test-dir", default=str(ML_DIR / "data/public_only/test_public"), help="folder with images/ and labels/")
    ap.add_argument("--out", default=str(ML_DIR / "models"))
    ap.add_argument("--model-version", default="yolo26n-public-v1")
    ap.add_argument("--device", default="mps")
    args = ap.parse_args(argv)

    from ultralytics import YOLO

    names = load_names(Path(args.data))
    classes = [names[i] for i in sorted(names)]
    weights, test_dir, out = Path(args.weights).resolve(), Path(args.test_dir), Path(args.out)
    model = YOLO(str(weights))

    def predict(path: Path):
        r = model.predict(str(path), imgsz=640, conf=0.05, device=args.device, verbose=False)[0]
        return [(names[int(c)], tuple(map(float, b)), float(s)) for c, b, s in zip(r.boxes.cls, r.boxes.xyxyn, r.boxes.conf)]

    try:
        ev, results = score_directory(test_dir / "images", test_dir / "labels", names, predict, conf_thr=CONFIDENCE, iou_thr=OVERLAP)
    except EvaluationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    matrix = confusion_matrix(results, classes, iou_thr=OVERLAP, conf_thr=CONFIDENCE)
    trained_at = datetime.fromtimestamp(weights.stat().st_mtime, UTC)
    card = card_dict(ev, matrix, classes, model_version=args.model_version, trained_at=trained_at, datasets=DATASETS)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(weights, out / "best.pt")
    (out / "model_card.json").write_text(json.dumps(card, indent=2) + "\n")
    print(json.dumps(card, indent=2))
    print(f"\nsaved {out / 'model_card.json'} and {out / 'best.pt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Run the new tests.** Expected: pass.
- [x] **Step 5: Run the script** from `services/api`: `uv run --group ml python -m ml.model_card`. Check, with your own eyes against `ml/reports/public_only.json`: hole found 24 / missed 2 / false alarms 4, stain 18 / 11 / 4, thread_fault 8 / 24 / 4; test_defective 59, test_clean 0, `clean_false_alarm_rate` null. **If any number differs, stop and find out why before going on** (the report was produced by `ml.evaluate` with the same matching; a difference means a bug in one of them). Also confirm row sums in the printed matrix: hole row = 26, stain row = 29, thread_fault row = 32.
- [x] **Step 6: Check the files will be committed:** `command git check-ignore -v services/api/ml/models/best.pt services/api/ml/models/model_card.json` must print nothing (exit 1). Confirm `best.pt` is 5.4 MB.
- [x] **Step 7: Full suite twice;** green.
- [x] **Step 8: Commit.**

```bash
git add services/api/ml/model_card.py services/api/tests/test_ml_model_card.py services/api/ml/models
git commit -m "Build the model card from the held-out photos and ship the weights with it"
```

---

### Task 5: The real model-card route, and the screen's honesty about an unmeasured rate

**Files:**
- Modify: `services/api/app/modules/qc/vision.py` (add `read_card`, `NO_CARD`)
- Modify: `services/api/app/modules/qc/router.py` (the `model_card` route)
- Modify: `services/api/app/modules/qc/examples.py` (remove `MODEL_CARD` and the `ModelCard` import)
- Modify: `apps/web/src/pages/qc/ModelCard.tsx`, `apps/web/src/pages/qc/ModelCard.test.tsx`
- Modify: `package.json` (`dev:api`)
- Test: `services/api/tests/test_qc_model_card.py`

**Interfaces:**
- Consumes: the committed `ml/models/model_card.json` (Task 4); `CARD_PATH` (Task 2).
- Produces: `read_card() -> schemas.ModelCard` (never raises).

- [ ] **Step 1: Write the failing backend tests.** `services/api/tests/test_qc_model_card.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail** (the route still returns example data, so `available` is False and the first assertions fail).

- [ ] **Step 3: Implement.** In `vision.py` add `from pydantic import ValidationError` to the imports and append:

```python
NO_CARD = s.ModelCard(available=False, model_version=None, trained_at=None, datasets=[], test_defective=0, test_clean=0,
                      clean_false_alarm_rate=None, per_class=[], confusion_labels=[], confusion_matrix=[])


def read_card() -> s.ModelCard:
    """The saved model card, or 'not evaluated yet' if the file is missing or unusable (the page must not break)."""
    try:
        return s.ModelCard(available=True, **json.loads(CARD_PATH.read_text()))
    except FileNotFoundError:
        return NO_CARD
    except (OSError, ValueError, TypeError, ValidationError):
        logger.warning("the model card file %s is unusable", CARD_PATH, exc_info=True)
        return NO_CARD
```

Router: `def model_card() -> s.ModelCard: return vision.read_card()`. In `examples.py` delete the `MODEL_CARD = ModelCard(...)` block and `ModelCard` from the import list.

- [ ] **Step 4: Run the backend tests;** pass. Mutation checks: change the `labels[-1]` or break one matrix cell in a temporary copy of the card (the sums test fails); make `read_card` return `NO_CARD` always (the route test fails).
- [ ] **Step 5: Web test first.** In `apps/web/src/pages/qc/ModelCard.test.tsx` add, after `WEAK`:

```tsx
const UNMEASURED = { ...GOOD, test_clean: 0, clean_false_alarm_rate: null }
```

and a new block:

```tsx
describe('ModelCard when false alarms on clean cloth were not measured', () => {
  it('says "Not measured", never 0%', async () => {
    mockApi({ GET: { '/api/qc/model-card': UNMEASURED } })
    renderPage(<ModelCard />)
    await screen.findByText('yolo-v1')
    const kpi = screen.getByText('False alarms on clean cloth').closest('.kpi') as HTMLElement
    expect(kpi).toHaveTextContent(/not measured/i)
    expect(kpi).not.toHaveTextContent('0%')
  })

  it('calls the model unvalidated, not "below the bar"', async () => {
    mockApi({ GET: { '/api/qc/model-card': UNMEASURED } })
    renderPage(<ModelCard />)
    expect(await screen.findByText(/not yet validated/i)).toBeInTheDocument()
    expect(screen.queryByText(/below the bar/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/meets the bar/i)).not.toBeInTheDocument()
  })
})
```

Run `cd apps/web && npx vitest run src/pages/qc/ModelCard.test.tsx` — Expected: the two new tests fail (the KPI shows `0%`; the alert says "below the bar").

- [ ] **Step 6: Edit `ModelCard.tsx`.** In `Evaluated`, replace the `<Alert>` block with:

```tsx
      <Alert tone={c.clean_false_alarm_rate === null || good ? 'info' : 'error'}>
        {c.clean_false_alarm_rate === null
          ? 'Not yet validated: false alarms on clean cloth have not been measured (the test photos had no clean cloth), so this model is offered as an unvalidated suggestion only.'
          : good
            ? `This model meets the bar: it finds at least ${pct(HOLE_RECALL_BAR)} of holes with no more than ${pct(FALSE_ALARM_BAR)} false alarms on clean cloth.`
            : `This model is below the bar (holes found at least ${pct(HOLE_RECALL_BAR)}, false alarms at most ${pct(FALSE_ALARM_BAR)}), so it is offered as a supporting suggestion only.`}
      </Alert>
```

and replace the `<KpiCard label="False alarms on clean cloth" .../>` with:

```tsx
        {c.clean_false_alarm_rate === null ? (
          <div className="kpi">
            <span className="kpi-label">False alarms on clean cloth</span>
            <span className="kpi-value">Not measured</span>
            <span className="muted text-sm">no clean test photos yet</span>
          </div>
        ) : (
          <KpiCard
            label="False alarms on clean cloth"
            value={c.clean_false_alarm_rate * 100}
            format={(n) => `${Math.round(n)}%`}
            tone={c.clean_false_alarm_rate > FALSE_ALARM_BAR ? 'danger' : undefined}
          />
        )}
```

Re-run the file's tests (all, new and old, pass), then `npx vitest run` (whole web suite), `npx tsc -b`, `npx oxlint` — all clean. (The tone is `info` for an unmeasured rate, so an unvalidated model is not announced as an error.)

- [ ] **Step 7: `package.json`:** change `dev:api` to `uv run --directory services/api --group ml uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` so a fresh clone installs the vision libraries (the model cannot run without them).
- [ ] **Step 8: Remove the now-unused example** from `examples.py` (see Files), run `grep -rn "MODEL_CARD" services/api` (nothing left), full backend suite twice, green; `test_committed_contract_matches_the_code` passes.
- [ ] **Step 9: Hritwik's server and app.** If `:8000` is up, `GET /api/health` answers; open the model-card page in his running app to see the real card.
- [ ] **Step 10: Commit.**

```bash
git add services/api/app/modules/qc services/api/tests/test_qc_model_card.py apps/web/src/pages/qc package.json
git commit -m "Serve the real model card and show an unmeasured false-alarm rate honestly"
```

---

### Task 6: Prove it on a real server

**Files:** modify this plan only (no code unless the live check finds a bug: then fix it test-first and say so).

- [ ] **Step 1: Throwaway database and server.** `lsof -nP -iTCP:8000 -iTCP:3000 -iTCP:8123 -sTCP:LISTEN`; `export DATABASE_URL=postgresql+psycopg://localhost:5432/everest_livecheck`; `createdb everest_livecheck`; from the repo root `npm run db:migrate && npm run db:seed`; start `cd services/api && uv run --group ml uvicorn app.main:app --host 127.0.0.1 --port 8123` in the background. Log in as `qc` (the dev password `seed_dev.py` prints) with `POST /api/auth/login`, keeping the cookie.
- [ ] **Step 2: A held-out photo against `ml.show_examples`.** Run `uv run --group ml python -m ml.show_examples` and note its "ALL FOUND" photo and its guesses. Upload that same photo (`POST /api/uploads`, multipart) and `POST /api/qc/analyze` with the returned path. The boxes must agree with the example's guesses (same defect types, same positions after converting centre/corner form to top-left+size, same confidences to two decimals). Record any difference and explain it.
- [ ] **Step 3: The phone-rotation check, empirically.** With Pillow, take that photo P and make Q = `P.rotate(90, expand=True)` saved as JPEG with EXIF orientation 6 (a sideways file that displays upright). Upload Q and analyze. Its boxes must equal P's (within 0.01). Then open the photo in the browser/app and look: the overlay must sit on the defect. Record the result.
- [ ] **Step 4: Bad inputs on the real server.** A file with a valid JPEG header followed by garbage: expect 422 "Could not read this photo"; a path to a deleted upload: 404; a wrong role: 403. A truncated real JPEG: 422.
- [ ] **Step 5: Model trouble on the real server.** Temporarily rename `ml/models/best.pt`, restart, analyze: 200 with `available=false` and the "missing" reason; restore it and analyze again: it works without restarting the server (a failure is not remembered). Do the same once for a garbage `best.pt` (restore afterwards, check `git status` shows no change to the committed weights).
- [ ] **Step 6: Speed and memory.** Time the first and second analyze request; record `ps -o rss= -p <server pid>` before and after (8 GB Mac, with his dev server running if it is). Fire 4 analyze requests at once and confirm all return 200.
- [ ] **Step 7: The model-card route and screens.** `GET /api/qc/model-card` as `qc`, `owner`, `supervisor` (200) and `accountant`, `buyer` (403); the body equals the committed file. Look at the model-card page and the QC inspect page in the browser against this server (take the photo flow through to a recorded inspection with the AI box shown).
- [ ] **Step 8: Adversarial checklist, once, on the new code and on any fix made here:** a 1×1 image and a very wide strip (the box maths); a PNG with transparency and a greyscale JPEG (the colour handling); an 8 MB photo (time); `photo_path` with `uploads/` plus 32 hex characters and the wrong extension; two inspectors analysing the same photo at the same time; a photo analysed, then the same one with a different rotation tag; the card file replaced by a bigger valid card while the server runs (read fresh each request, so the page updates).
- [ ] **Step 9: Clean up and re-check the other half.** Stop the server, `dropdb everest_livecheck`, confirm nothing listens on 8123 and only `everest` and `everest_test` remain. If his servers are running, re-check `GET /api/health`, `/api/qc/queue` and `/api/qc/model-card` (200s); his database needs no migration for B8.

---

### Task 7: Close-out sync

**Files:** this plan, `docs/plans/README.md`, `docs/plans/BV-vision-spike.md`, `docs/specs/2026-10-11-vision-endpoint-design.md`, `docs/specs/2026-10-10-textile-mill-design.md` (§9 status line only), `docs/HRITWIK_TEAM_NOTES.md`, the project memory.

- [ ] **Step 1: Live date check** (`date`) before writing any date.
- [ ] **Step 2: Mark B8 complete** in this plan (Status line with the real numbers from Task 6: test counts, speed, memory, the rotation result) and in `docs/plans/README.md` (rows B8 and R7); update the headers (summary + last updated) of every document touched.
- [ ] **Step 3: BV notes.** Add the shipped model's location (`ml/models/`), the card, and that R9 (clean images) is still the open step; do not claim a verdict beyond "inconclusive".
- [ ] **Step 4: Team note** (top of `docs/HRITWIK_TEAM_NOTES.md`, newest first, `From: Hritwik → Ridanshi`): `/qc/analyze` and `/qc/model-card` are real; the contract is unchanged; I edited `ModelCard.tsx` and its test (an unmeasured rate shows "Not measured" and "Not yet validated" instead of 0% and "below the bar"), please review; `dev:api` now starts with `--group ml`; the message is a fixed "Unvalidated first version" string; the verdict rule (nothing found → pass, anything → rework, never reject).
- [ ] **Step 5: Memory.** Update the project state memory and its index line (B8 done; what is next: B9 demo scenarios, review of Ridanshi's unpushed branch, the pre-jury checklist).
- [ ] **Step 6: Authorship scan** of everything staged (`git diff --cached` and the changed paths), as in the repo's pre-jury checklist.
- [ ] **Step 7: Commit** (no push).

```bash
git add docs
git commit -m "Close B8: the vision endpoint and the model card passed the live check"
```

---

## Done when

- The full backend suite is green twice; the web suite, `tsc -b` and `oxlint` are clean; every mutation listed in Tasks 1–5 makes a test fail.
- `ml.model_card` reproduces the saved report's per-class numbers exactly, and the committed card's matrix rows and columns add up to them.
- On a real server a held-out photo gets the same boxes as `ml.show_examples`; a sideways phone photo's boxes land on the defect; every bad input is a clean 422/404; every model problem is a 200 with `available=false`; the model-card page shows "Not measured".
- `contracts/` is byte-identical; `docs/plans/README.md` marks B8 and R7 done; the plan's Status, the spec header, the team note and the memory are current.
