"""Show what the detector does on a few held-out photos: the answer key next to the model's guesses, as text and as pictures.

Run (from services/api):  uv run --group ml python -m ml.show_examples
It picks one photo where every defect is found (with two kinds of defect) and one where something is missed, prints both and
saves a picture of each in ml/demo_examples/: GREEN boxes are the real defects (the label file), RED boxes are the model's
guesses (confidence 0.25 or more, with the confidence written next to them). Needs the trained model and the test photos
on this machine (they are git-ignored); `--device cpu` on a computer without an Apple GPU.
"""
import argparse
from dataclasses import dataclass
from pathlib import Path

from ml.metrics import Box, ImageResult, evaluate, iou
from ml.yolo_labels import parse_labels

ML_DIR = Path(__file__).resolve().parent
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
IOU_THRESHOLD = 0.3          # the same overlap rule ml.evaluate uses to decide that a guess found a real defect


@dataclass
class Row:
    name: str
    truths: list[tuple[str, Box]]
    preds: list[tuple[str, Box, float]]
    found: int
    missed: int
    false_alarms: int
    kinds: int               # how many different defect types the photo really has


def pick_examples(rows: list[Row]) -> list[tuple[str, Row]]:
    """The first photo with two kinds of defect that were all found, and the first where something was found and something missed."""
    all_found = next((r for r in rows if r.kinds >= 2 and r.missed == 0), None)
    some_missed = next((r for r in rows if r.missed >= 1 and r.found >= 1), None)
    return [(title, r) for title, r in (("ALL FOUND", all_found), ("SOMETHING MISSED", some_missed)) if r is not None]


def describe(truths: list[tuple[str, Box]], preds: list[tuple[str, Box, float]], label_lines: list[str]) -> list[str]:
    """Plain words for one photo: each file line, each real defect, and each guess with whether it matches one."""
    lines = ["ANSWER KEY (the label file: class, x centre, y centre, width, height, each as a fraction of the picture):"]
    lines += [f"   file line : {text}" for text in label_lines]
    lines += [f"   real defect: {cls:13s} box=({b[0]:.2f}, {b[1]:.2f}, {b[2]:.2f}, {b[3]:.2f})" for cls, b in truths]
    lines.append("MODEL PREDICTIONS (confidence 0.25 or more, best first):")
    unmatched = list(truths)
    for cls, box, score in sorted(preds, key=lambda p: -p[2]):
        hit = next((t for t in unmatched if t[0] == cls and iou(box, t[1]) >= IOU_THRESHOLD), None)
        if hit:
            unmatched.remove(hit)                      # a real defect can be found only once
        verdict = "matches a real defect" if hit else "FALSE ALARM"
        lines.append(f"   predicts  : {cls:13s} confidence={score:.2f} box=({box[0]:.2f}, {box[1]:.2f}, {box[2]:.2f}, {box[3]:.2f})  -> {verdict}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", default=str(ML_DIR / "runs/public_only/weights/best.pt"))
    ap.add_argument("--data", default=str(ML_DIR / "data/public_only/data.yaml"), help="the dataset YAML (for the class names)")
    ap.add_argument("--test-dir", default=str(ML_DIR / "data/public_only/test_public"), help="folder with images/ and labels/")
    ap.add_argument("--out", default=str(ML_DIR / "demo_examples"))
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--device", default="mps")
    args = ap.parse_args(argv)

    from PIL import Image, ImageDraw
    from ultralytics import YOLO

    from ml.evaluate import load_names

    names, test_dir, out = load_names(Path(args.data)), Path(args.test_dir), Path(args.out)
    model = YOLO(args.weights)
    rows: list[Row] = []
    for image in sorted(p for p in (test_dir / "images").iterdir() if p.suffix.lower() in IMAGE_SUFFIXES):
        truths = parse_labels((test_dir / "labels" / (image.stem + ".txt")).read_text(), names)
        result = model.predict(str(image), imgsz=640, conf=0.05, device=args.device, verbose=False)[0]
        preds = [(names[int(c)], tuple(map(float, b)), float(s))
                 for c, b, s in zip(result.boxes.cls, result.boxes.xyxyn, result.boxes.conf) if float(s) >= args.conf]
        ev = evaluate([ImageResult(truths, preds)], iou_thr=IOU_THRESHOLD, conf_thr=args.conf)
        rows.append(Row(image.name, truths, preds, sum(c.found for c in ev.per_class.values()),
                        sum(c.missed for c in ev.per_class.values()), sum(c.false_alarms for c in ev.per_class.values()),
                        len({cls for cls, _ in truths})))
    picked = pick_examples(rows)
    if not picked:
        print("No photo in the test folder fits the two examples (two kinds all found; something missed).")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    report: list[str] = []
    for number, (title, row) in enumerate(picked, start=1):
        label_lines = (test_dir / "labels" / (Path(row.name).stem + ".txt")).read_text().strip().splitlines()
        block = [f"==================== EXAMPLE {number}: {title} ({row.name}) ====================",
                 *describe(row.truths, row.preds, label_lines),
                 f"RESULT for this photo: found {row.found}, missed {row.missed}, false alarms {row.false_alarms}"]
        picture = Image.open(test_dir / "images" / row.name).convert("RGB")
        width, height = picture.size
        draw = ImageDraw.Draw(picture)
        for cls, b in row.truths:
            draw.rectangle([b[0] * width, b[1] * height, b[2] * width, b[3] * height], outline=(0, 200, 0), width=4)
            draw.text((b[0] * width + 4, b[1] * height + 2), f"REAL {cls}", fill=(0, 200, 0))
        for cls, b, score in row.preds:
            draw.rectangle([b[0] * width, b[1] * height, b[2] * width, b[3] * height], outline=(230, 0, 0), width=2)
            draw.text((b[0] * width + 4, b[3] * height - 12), f"{cls} {score:.2f}", fill=(230, 0, 0))
        target = out / f"example_{number}_{title.lower().replace(' ', '_')}.png"
        picture.save(target)
        block.append(f"picture saved: {target}")
        print("\n".join(block) + "\n")
        report += block + [""]
    (out / "examples.txt").write_text("\n".join(report))
    print(f"text saved: {out / 'examples.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
