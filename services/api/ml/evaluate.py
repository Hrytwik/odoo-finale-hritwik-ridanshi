"""Score a trained detector on held-out photos and apply the spike's kill criteria.

Run: uv run --group ml python -m ml.evaluate --weights ml/runs/<run>/weights/best.pt --data ml/data/own/data.yaml
"""
import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from ml.metrics import Box, Decision, Evaluation, ImageResult, decide, evaluate
from ml.yolo_labels import LabelError, parse_labels

ML_DIR = Path(__file__).resolve().parent
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}

Predict = Callable[[Path], list[tuple[str, Box, float]]]


class EvaluationError(RuntimeError):
    pass


def score_directory(images_dir: Path, labels_dir: Path, names: dict[int, str], predict: Predict,
                    conf_thr: float = 0.25, iou_thr: float = 0.3) -> tuple[Evaluation, list[ImageResult]]:
    paths = sorted(p for p in Path(images_dir).iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not paths:
        raise EvaluationError(f"no images found in {images_dir}")
    results = []
    for path in paths:
        label_file = Path(labels_dir) / (path.stem + ".txt")
        if not label_file.is_file():
            raise EvaluationError(
                f"missing label file for {path.name}: every test photo needs one "
                "(an empty file means clean cloth, but a missing file is never assumed to be clean)"
            )
        try:
            truths = parse_labels(label_file.read_text(), names)
        except LabelError as exc:
            raise EvaluationError(f"{label_file.name}: {exc}") from None
        results.append(ImageResult(truths=truths, preds=predict(path)))
    return evaluate(results, iou_thr=iou_thr, conf_thr=conf_thr), results


def report_dict(ev: Evaluation, decision: Decision, args: dict) -> dict:
    return {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "settings": args,
        "test_photos": {"defective": ev.defective_images, "clean": ev.clean_images},
        "clean_false_alarm_rate": ev.clean_false_alarm_rate,
        "per_class": {
            c: {"found": r.found, "missed": r.missed, "false_alarms": r.false_alarms, "recall": r.recall, "precision": r.precision}
            for c, r in sorted(ev.per_class.items())
        },
        "verdict": decision.verdict,
        "reason": decision.reason,
    }


def load_names(data_yaml: Path) -> dict[int, str]:
    import yaml  # installed with ultralytics

    names = yaml.safe_load(Path(data_yaml).read_text())["names"]
    return {int(k): v for k, v in names.items()} if isinstance(names, dict) else dict(enumerate(names))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", required=True, help="the dataset YAML (used for the class names)")
    ap.add_argument("--test-dir", help="folder with images/ and labels/ to score; default: <data folder>/test")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.25, help="detections below this confidence are ignored")
    ap.add_argument("--device", default="mps")
    ap.add_argument("--name", default="spike")
    args = ap.parse_args(argv)

    from ultralytics import YOLO

    data = Path(args.data).resolve()
    names = load_names(data)
    model = YOLO(args.weights)

    def predict(path: Path):
        r = model.predict(str(path), imgsz=args.imgsz, conf=0.05, device=args.device, verbose=False)[0]
        return [(names[int(c)], tuple(map(float, b)), float(s)) for c, b, s in zip(r.boxes.cls, r.boxes.xyxyn, r.boxes.conf)]

    test_dir = Path(args.test_dir).resolve() if args.test_dir else data.parent / "test"
    try:
        ev, _ = score_directory(test_dir / "images", test_dir / "labels", names, predict, conf_thr=args.conf)
    except EvaluationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    decision = decide(ev)
    report = report_dict(ev, decision, vars(args))
    (ML_DIR / "reports").mkdir(exist_ok=True)
    out = ML_DIR / "reports" / f"{args.name}.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print(f"\nVERDICT: {decision.verdict.upper()} — {decision.reason}\n(report saved to {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
