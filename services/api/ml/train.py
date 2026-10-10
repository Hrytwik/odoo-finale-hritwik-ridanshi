"""Train the defect detector (the vision spike).

Smoke test (measures speed/memory on this machine): uv run --group ml python -m ml.train --smoke
Real run: uv run --group ml python -m ml.train --data ml/data/own/data.yaml --hours 1.0
"""
import argparse
import time
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", help="dataset YAML (own photos, optionally plus public data)")
    ap.add_argument("--weights", default="yolo26n.pt", help="pretrained starting point (nano size)")
    ap.add_argument("--hours", type=float, default=1.0, help="hard time limit; overrides --epochs")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=8, help="fixed: auto-sizing is CUDA only (8 GB RAM Mac: keep small)")
    ap.add_argument("--device", default="mps")
    ap.add_argument("--patience", type=int, default=20)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--name", default="spike")
    ap.add_argument("--smoke", action="store_true", help="one tiny epoch on a 1 MB sample dataset, to measure speed")
    args = ap.parse_args(argv)
    if not args.smoke and not args.data:
        ap.error("--data is required unless --smoke is given")

    from ultralytics import YOLO  # imported here so this module can be imported without the ml group

    model = YOLO(args.weights)
    settings = dict(
        data="coco8.yaml" if args.smoke else args.data,
        imgsz=320 if args.smoke else args.imgsz,
        batch=4 if args.smoke else args.batch,
        device=args.device, workers=args.workers, patience=args.patience,
        project=str(ML_DIR / "runs"), name="smoke" if args.smoke else args.name, exist_ok=True,
    )
    if args.smoke:
        settings["epochs"] = 1
    else:
        settings["epochs"], settings["time"] = args.epochs, args.hours
    start = time.time()
    model.train(**settings)
    print(f"\nTRAINING FINISHED in {(time.time() - start) / 60:.1f} minutes; "
          f"best weights: {ML_DIR / 'runs' / settings['name'] / 'weights' / 'best.pt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
