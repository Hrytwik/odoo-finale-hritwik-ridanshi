# B8 — Vision Endpoint and Model Card: Design

> **Summary:** Makes `POST /qc/analyze` run our fine-tuned YOLO detector on an uploaded cloth photo and `GET /qc/model-card` serve the measured held-out results (with a confusion matrix), both labelled as an unvalidated first version; covers the box conversion, the verdict rule, the unavailable path, the model-card file, tests and the live check.
> **Last updated:** 2026-10-11 01:43 IST
> **Status:** Draft for Hritwik's review (design approved in chat section by section on 2026-10-11)

Parent spec: `2026-10-10-textile-mill-design.md` §9 (Vision QC). Background and numbers: `docs/plans/BV-vision-spike.md`.

## 1. Goal and what is out of scope

Make the two QC vision endpoints real and honest. `/qc/analyze` runs the local fine-tuned detector (`yolo26n.pt` fine-tuned on the 416 public Roboflow training photos; weights `best.pt`, 5.4 MB; no internet needed) and returns boxes the inspector can confirm or override. `/qc/model-card` shows only measured numbers, and says plainly that the false-alarm rate on clean cloth is **not measured**.

The contract types (`AnalyzeOut`, `AiSuggestion`, `Box`, `ModelCard`) do not change, so Ridanshi's screens need no edits. QC works fully without the model (parent spec §9).

Out of scope: measuring the clean-cloth false-alarm rate (parked, BV / R9), training anything new, the vision-capable language-model fallback, colour-mismatch detection.

## 2. Pieces

- **New module `app/modules/qc/vision.py`** does two jobs: load the weights and run them on one photo (returning boxes and a verdict), and read the saved model-card file and return it in the contract's shape. The routes in `qc/router.py` stay thin and call it instead of returning `ex.ANALYZE` and `ex.MODEL_CARD`.
- **Box conversion.** `PhotoWithBoxes` places `x`,`y` at CSS `left`,`top`, so they are the box's **top-left corner** as 0–1 fractions of the photo. The detector gives corner pairs (`xyxyn`: left, top, right, bottom). So `x = left`, `y = top`, `w = right − left`, `h = bottom − top`; results are clamped to 0–1 with `w`,`h` kept positive.
- **Class names** already match the contract's `DefectType` (`hole`, `stain`, `thread_fault`); no mapping.
- **The model card comes from a file**, written once by a script in the `ml` group, never computed at serving time. The API needs neither Ultralytics nor the test photos to serve it.
- **Ultralytics stays in the optional `ml` group.** Its import in `vision.py` is lazy and guarded.
- **Committed files** (parent spec §9): `services/api/ml/models/best.pt` and `services/api/ml/models/model_card.json`. The README already credits Ultralytics (AGPL-3.0) and the Roboflow dataset (CC BY 4.0).

## 3. `POST /qc/analyze`

Roles: unchanged (`inspectors`). Steps, in order:

1. `check_upload_path` on `photo_path` (the same function record-inspection uses). A free-typed path or a URL gives the usual 422. A valid path whose file is missing gives 404 "Photo not found".
2. Load the model **once, lazily**, on the first request; reuse it afterwards. A failed load is **not** cached, so fixing the cause works on the next request. (Lazy keeps server start and the auto-reloading dev server light on the 8 GB Mac.)
3. Run the detector at image size 640 and confidence **0.25** — the same settings the evaluation used, so the model card describes exactly what the endpoint does. One lock serializes calls; whether YOLO is safe under concurrent threads is **unverified**, so it is not assumed.
4. Convert boxes (section 2), sort by confidence, cut to the contract's maximum of 100.
5. **Verdict:** no boxes → `pass`; one or more → `rework`; **never `reject`** (scrapping a roll stays a human decision). The inspector confirms or overrides; the server records `overrode_ai` when the final verdict differs.
6. **Always label it.** The response message is a fixed string: unvalidated first version, trained on public photos only, nothing found does not mean clean, thread faults are often missed (real recall 0.25, stains 0.62, holes 0.92 on the public test split).

**Model unavailable** (weights missing, Ultralytics not installed, load failure): HTTP 200 with `available=false`, `suggestion=null` and a plain reason. **Corrupt image** that passed the upload check's header test: 422 "Could not read this photo" (the user's problem, not the model's).

`model_version` comes from `model_card.json`; if the card file is absent, from the weights file name.

## 4. `GET /qc/model-card`

Roles: unchanged. Reads `ml/models/model_card.json`; missing file → `available=false`.

The script (run in the `ml` group, built on the existing `ml.evaluate` scoring) scores `best.pt` on the held-out public test split and writes the card. It adds the missing **confusion matrix**: rows are what was really on the photo, columns what the model said, over the 3 classes plus a "nothing" row and column. The "nothing" column of a row counts missed defects; the "nothing" row of a column counts false alarms; the diagonal counts found-and-correctly-named. A guess matches a real defect when overlap is at least 0.3 (`IOU_THRESHOLD` in `ml/show_examples.py`, the same rule `ml.evaluate` uses), so the matrix agrees with the per-class numbers.

The card states: test set 59 defective photos, 0 clean; `clean_false_alarm_rate = null` (shown as "not measured"); model `yolo26n` fine-tuned on 416 public photos; dataset name, URL and licence; verdict **inconclusive**. Real numbers only.

## 5. Tests

Without the weights (a fake detector stands in), following the existing `test_ml_*.py` pattern:
- **Box conversion:** boxes at all four edges, full-photo, tiny, swapped corners; every result within 0–1, `w` and `h` positive.
- **Verdict rule:** zero boxes → pass, one or more → rework, never reject; more than 100 detections cut to 100 by highest confidence.
- **Route behaviour:** bad path → 422, valid path with no file → 404, a non-inspector role → 403, model unavailable → 200 with `available=false`.
- **Confusion matrix invariant:** each row sums to the class's found + missed; the diagonal equals `found`.
- **Model card:** missing file → `available=false`; the committed file passes the contract schema and has `clean_false_alarm_rate` null.

## 6. Live check (real server, real weights)

- One held-out test photo through `/qc/analyze`; boxes agree with `ml.show_examples`.
- A phone photo with an EXIF rotation tag: **unverified** whether the detector applies the same rotation a browser does, so check that boxes land correctly on screen.
- A corrupt file with a valid image header gives 422, not a crash.
- First and second request time, and memory with the dev server running (8 GB Mac).
- Open the QC screen and the model-card page in Ridanshi's app. No new migrations, so no dev-database step.

## 7. Build order

1. Box conversion and verdict rule, with tests.
2. `vision.py` loader: lazy load, lock, unavailable path.
3. `/qc/analyze` route wiring.
4. Confusion-matrix script; run it to produce `model_card.json`; commit `best.pt` and the card.
5. `/qc/model-card` route.
6. Live check.
7. Close-out sync: plan file `B8-vision-endpoint.md`, the plan table in `docs/plans/README.md`, the BV notes, memory, commit. Authorship scan before the commit. No push.
