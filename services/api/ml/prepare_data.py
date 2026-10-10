"""Build one training dataset from our own photos and (optionally) the public Roboflow subset.

Run: uv run --group ml python -m ml.prepare_data --own ml/data/own --public ml/data/public/roboflow_subset --out ml/data/combined
Leave out --public for variant A (own photos only). The own `test` folder is never read here.
"""
import argparse
import hashlib
import shutil
from pathlib import Path

OURS = ["hole", "stain", "thread_fault"]
# Roboflow ids: 0 color, 1 hole, 2 thread. Mapped by meaning (the 'color' boxes are dark ink-like smears = stains).
ROBOFLOW_TO_OURS = {0: 1, 1: 0, 2: 2}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
MIN_OWN_FOR_VALIDATION = 10
VAL_FRACTION = 0.15


class PrepareError(ValueError):
    pass


def remap_label_text(text: str, id_map: dict[int, int]) -> str:
    out = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        parts = raw.split()
        if len(parts) != 5:
            raise PrepareError(f"line {number}: expected 5 numbers, got {len(parts)}")
        try:
            class_id = int(parts[0])
        except ValueError:
            raise PrepareError(f"line {number}: class id is not a number") from None
        if class_id not in id_map:
            raise PrepareError(f"line {number}: unknown class {class_id}")
        out.append(" ".join([str(id_map[class_id]), *parts[1:]]))
    return "\n".join(out) + "\n" if out else ""


def _items(split_dir: Path) -> list[tuple[Path, Path]]:
    images = sorted(p for p in (split_dir / "images").iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    pairs = []
    for img in images:
        label = split_dir / "labels" / (img.stem + ".txt")
        if not label.is_file():
            raise PrepareError(f"missing label file for {img.name} (an empty file means clean cloth)")
        pairs.append((img, label))
    return pairs


def _copy(pairs, out: Path, split: str, prefix: str, id_map: dict[int, int] | None) -> int:
    (out / split / "images").mkdir(parents=True, exist_ok=True)
    (out / split / "labels").mkdir(parents=True, exist_ok=True)
    for img, label in pairs:
        text = label.read_text()
        text = remap_label_text(text, id_map) if id_map is not None else remap_label_text(text, {i: i for i in range(len(OURS))})
        shutil.copyfile(img, out / split / "images" / f"{prefix}_{img.name}")
        (out / split / "labels" / f"{prefix}_{img.stem}.txt").write_text(text)
    return len(pairs)


def _own_split(pairs):
    """Stable validation pick (by filename hash, so it never depends on order); only when there are enough photos."""
    if len(pairs) < MIN_OWN_FOR_VALIDATION:
        return pairs, []
    ranked = sorted(pairs, key=lambda p: hashlib.md5(p[0].name.encode()).hexdigest())
    n_val = max(1, round(len(pairs) * VAL_FRACTION))
    val = ranked[:n_val]
    return [p for p in pairs if p not in val], val


def build_dataset(out: Path, public: Path | None, own: Path | None) -> dict:
    out = Path(out)
    for sub in ("train", "val", "test_public"):                      # only what this tool creates; never the whole folder
        shutil.rmtree(out / sub, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    stats = {"train_images": 0, "val_images": 0, "test_public_images": 0}
    if public is not None:
        stats["train_images"] += _copy(_items(Path(public) / "train"), out, "train", "public", ROBOFLOW_TO_OURS)
        stats["val_images"] += _copy(_items(Path(public) / "valid"), out, "val", "public", ROBOFLOW_TO_OURS)
        if (Path(public) / "test").is_dir():                # the dataset's own test split, kept apart, class ids remapped
            stats["test_public_images"] += _copy(_items(Path(public) / "test"), out, "test_public", "public", ROBOFLOW_TO_OURS)
    if own is not None:
        train, val = _own_split(_items(Path(own) / "train"))
        stats["train_images"] += _copy(train, out, "train", "own", None)
        stats["val_images"] += _copy(val, out, "val", "own", None)
    if stats["val_images"] == 0:
        raise PrepareError(f"need a validation set: add public data, or at least {MIN_OWN_FOR_VALIDATION} own training photos")
    if stats["train_images"] == 0:
        raise PrepareError("no training images found")
    names = "\n".join(f"  {i}: {n}" for i, n in enumerate(OURS))
    (out / "data.yaml").write_text(f"path: {out.resolve()}\ntrain: train/images\nval: val/images\nnames:\n{names}\n")
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--own", type=Path, help="folder with train/ (and test/, which is never read)")
    ap.add_argument("--public", type=Path, help="the unzipped Roboflow subset (variant B); omit for variant A")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.own is None and args.public is None:
        ap.error("give --own and/or --public")
    try:
        stats = build_dataset(args.out, public=args.public, own=args.own)
    except PrepareError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"built {args.out}: {stats['train_images']} training images, {stats['val_images']} validation images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
