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
