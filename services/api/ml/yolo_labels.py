"""Read YOLO-format label text (one defect per line: class x_center y_center width height, all 0-1)."""
from ml.metrics import Box


class LabelError(ValueError):
    pass


def parse_labels(text: str | None, names: dict[int, str]) -> list[tuple[str, Box]]:
    """A missing or empty file means the photo shows clean cloth, which is how the test set marks clean photos."""
    if text is None:
        return []
    out: list[tuple[str, Box]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            raise LabelError(f"line {number}: expected 5 numbers, got {len(parts)}")
        try:
            class_id = int(parts[0])
            xc, yc, w, h = (float(p) for p in parts[1:])
        except ValueError:
            raise LabelError(f"line {number}: not numbers: {line!r}") from None
        if class_id not in names:
            raise LabelError(f"line {number}: unknown class {class_id}")
        if not (0 <= xc <= 1 and 0 <= yc <= 1 and 0 < w <= 1 and 0 < h <= 1):
            raise LabelError(f"line {number}: values must be between 0 and 1 (and the size above 0)")
        out.append((names[class_id], (max(0.0, xc - w / 2), max(0.0, yc - h / 2), min(1.0, xc + w / 2), min(1.0, yc + h / 2))))
    return out
