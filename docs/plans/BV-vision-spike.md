# BV — Vision QC Spike

> **Summary:** A time-boxed experiment (3 hours of work) that answers one question: can a small YOLO model, trained on a few public images plus our own phone photos, find holes in the cloth we will show at the demo? Includes the photo checklist, labelling steps, training and evaluation commands, and the kill criteria (computed by tested code).
> **Last updated:** 2026-10-10

**The question:** can a small object detector find holes (and ideally stains and thread faults) in cloth photographed with a phone, on cloth it has never seen?

**Kill criteria** (spec §9), measured on **held-out photos only**, at least 30 defective and 30 clean:
- holes found ≥ 80% **and** false alarms on clean cloth ≤ 20% → vision QC is a headline feature;
- otherwise → vision becomes a labelled "unvalidated AI suggestion" (a vision-capable language model, no training, needs internet);
- if that is unavailable → manual QC only. The rest of the system works either way.

These thresholds live in `services/api/ml/metrics.py` (`decide()`), with unit tests, so the verdict is computed, not eyeballed.

## What is verified and what is not

| Verified (Ultralytics docs, fetched 2026-10-10) | Not verified |
|---|---|
| Pretrained nano model `yolo26n.pt`; YOLO11 is the previous generation | Training speed on this Mac (M2, **8 GB RAM**, 31 GB free disk) |
| Apple GPU training: `device="mps"` | Whether 8 GB is enough at `imgsz=640`; the plan starts at a small batch |
| A `time=` hour limit exists (overrides `epochs`); `batch=-1` auto-sizing is CUDA only | How long labelling takes (the plan's estimate is a guess) |
| Dataset format: YAML with `path`, `train`, `val`, `test`, `names` + one label `.txt` per image | Licences of every public dataset (not shown on the pages I fetched) |
| Licence of the library: AGPL-3.0 or Enterprise | Accuracy on our cloth (that is the spike) |

## Roles

- **Hritwik:** shoots the photos, labels them, runs the commands, reads the verdict.
- **Tooling (already in the repo, unit-tested):** the ML environment (`uv` group `ml`), `ml/metrics.py` (found / missed / false alarms and the kill-criteria decision), `ml/yolo_labels.py` (label-file parser), `ml/train.py`, `ml/evaluate.py`.

## Phase 1 — Shoot the photos (Hritwik)

**Cloth.** Four different pieces, labelled **A, B, C, D**: different colours and weaves (at least one plain light, one plain dark, one patterned). **Pieces A and B are for training. Pieces C and D are for the test and must never be used for training.** The point of the test is "cloth the model has never seen", like a judge handing us their own fabric.

**Make real defects** on a piece, then photograph it:
- **Holes:** snip with scissors (about 3 mm, 1 cm, 2 cm) and poke with a needle.
- **Stains:** a few dabs of tea, coffee or ink, let dry.
- **Thread faults:** snag a thread with a needle and pull a loop.
- Also photograph each piece **clean**, before you damage it.

**How to shoot.**
- Phone flat above the cloth on a table, about 25–40 cm away, one frame covers roughly 20×30 cm of cloth.
- Tap to focus. Discard blurry shots.
- Use two lighting setups: bright even light (window + desk lamp) and dimmer or warmer light, close to a venue.
- Vary the position so the defect is not always in the middle.
- Each photo: one or two defects at most, so labelling stays quick.

**How many.**

| Set | Pieces | Defective photos | Clean photos |
|---|---|---|---|
| Train | A, B | about 80 (mostly holes, some stains and thread faults) | about 20 |
| **Test** | C, D | **at least 30, each containing a hole** | **at least 30** |

**Naming.** `A_hole_001.jpg`, `A_stain_004.jpg`, `C_clean_012.jpg`: piece letter, defect, number. AirDrop them into `services/api/ml/data/own/raw/` (git-ignored). Keep the originals; never overwrite.

**Rules that keep the result honest.**
- Test photos are shot **after** the training photos, from different pieces, and are never seen by the training script.
- Do not re-label or "fix" test labels after seeing results.
- Cloth only: no faces, documents or anything private.

## Phase 2 — Label (Hritwik)

A free **Roboflow** account is the quickest way to draw boxes (free-tier limits not verified): create an *Object Detection* project with exactly these classes, in this order: `hole`, `stain`, `thread_fault`. Draw tight boxes around each defect. **Clean photos get no boxes.** Export in **YOLO** format, as two separate exports: one for the training photos, one for the test photos. Unzip so that you have `images/` and `labels/` next to each other. Colour mismatch is deliberately not a class (a detector cannot know the target shade).

Place them as:
```
services/api/ml/data/own/train/images, labels
services/api/ml/data/own/test/images, labels
```
Check: every test image has a `.txt` file; an **empty** file means clean cloth.

## Phase 3 — Train

Smoke test first (measures speed and memory on this Mac): `uv run --group ml python -m ml.train --smoke`. **Result on 2026-10-10:** it runs end to end on the Apple GPU (`MPS (Apple M2)`, PyTorch 2.14.1, Ultralytics 8.4.175); one epoch on 4 tiny images at 320 px took about 14 seconds with 0.83 GB peak memory in the main process. That only proves the pipeline works; training time on our real photos is still unmeasured. Then the real run, with a hard time limit:

```
uv run --group ml python -m ml.train --data ml/data/own/data.yaml --hours 1.0
```
Settings: `yolo26n.pt`, `device=mps`, small fixed batch, early stopping. Output goes to `ml/runs/` (git-ignored).

Optional variant B: add the public **Roboflow "Fabric Defect Detection Subset"** (594 images, classes colour/hole/thread, needs a free account) to the training set, and compare variant A (own photos only) with B on the same test set. **Do not include any public data in a committed model until its licence has been read on its official page and credited in the README.** AITEX (245 strips of 4096×256 px with pixel masks, 7 fabrics) needs tiling and mask-to-box conversion, so it is lower priority.

## Phase 4 — Evaluate and decide

```
uv run --group ml python -m ml.evaluate --weights ml/runs/<run>/weights/best.pt --data ml/data/own/data.yaml
```
It runs the model on the test images only, compares with your labels, prints found / missed / false alarms per class and the clean-cloth false alarm rate, and prints the **verdict** (`headline`, `fallback` or `inconclusive`), also saved as a JSON report. `inconclusive` means the test set is too small or has no holes: shoot more test photos, do not lower the bar.

## After the verdict

- **headline:** commit the small `best.pt` and the JSON report under `services/api/ml/models/`; plan B8 (the `/qc/analyze` endpoint and the model card page).
- **fallback / inconclusive after more photos:** plan B8 as "unvalidated suggestion" using a vision-capable language model, labelled on screen.
- Either way, record the real numbers here and in the model card, never the hoped-for ones.
