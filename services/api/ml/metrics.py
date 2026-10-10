"""Evaluation of a defect detector, plus the spike's kill criteria as code.

Pure Python on purpose (no numpy/torch), so it is unit-tested in the normal suite.
Boxes are (x1, y1, x2, y2); any consistent unit works because IoU is scale-free.
"""
from dataclasses import dataclass, field

Box = tuple[float, float, float, float]

# Kill criteria from the design (spec §9), measured on photos the model never trained on.
MIN_DEFECTIVE_IMAGES = 30
MIN_CLEAN_IMAGES = 30
HOLE_CLASS = "hole"
MIN_HOLE_RECALL = (4, 5)        # holes found >= 4/5 = 80%
MAX_CLEAN_ALARM_RATE = (1, 5)   # false alarms on clean cloth <= 1/5 = 20%


def iou(a: Box, b: Box) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


@dataclass
class ImageResult:
    truths: list[tuple[str, Box]]
    preds: list[tuple[str, Box, float]]


@dataclass
class ClassResult:
    found: int = 0
    missed: int = 0
    false_alarms: int = 0

    @property
    def recall(self) -> float | None:
        total = self.found + self.missed
        return self.found / total if total else None

    @property
    def precision(self) -> float | None:
        total = self.found + self.false_alarms
        return self.found / total if total else None


@dataclass
class Evaluation:
    per_class: dict[str, ClassResult] = field(default_factory=dict)
    clean_images: int = 0
    defective_images: int = 0
    clean_alarm_images: int = 0

    @property
    def clean_false_alarm_rate(self) -> float | None:
        return self.clean_alarm_images / self.clean_images if self.clean_images else None


def evaluate(images: list[ImageResult], iou_thr: float = 0.3, conf_thr: float = 0.25) -> Evaluation:
    """Greedy matching per image, highest confidence first; each real defect can be found once."""
    out = Evaluation()
    for img in images:
        preds = sorted((p for p in img.preds if p[2] >= conf_thr), key=lambda p: p[2], reverse=True)
        unmatched = list(img.truths)
        for cls, pbox, _ in preds:
            best, best_iou = None, 0.0
            for t in unmatched:
                score = iou(pbox, t[1]) if t[0] == cls else 0.0
                if score >= iou_thr and score > best_iou:
                    best, best_iou = t, score
            if best is None:
                out.per_class.setdefault(cls, ClassResult()).false_alarms += 1
            else:
                unmatched.remove(best)
                out.per_class.setdefault(cls, ClassResult()).found += 1
        for cls, _ in unmatched:
            out.per_class.setdefault(cls, ClassResult()).missed += 1
        if img.truths:
            out.defective_images += 1
        else:
            out.clean_images += 1
            if preds:
                out.clean_alarm_images += 1
    return out


@dataclass
class Decision:
    verdict: str  # "headline" | "fallback" | "inconclusive"
    reason: str


def decide(ev: Evaluation) -> Decision:
    if ev.defective_images < MIN_DEFECTIVE_IMAGES:
        return Decision("inconclusive", f"only {ev.defective_images} defective test photos (need {MIN_DEFECTIVE_IMAGES})")
    if ev.clean_images < MIN_CLEAN_IMAGES:
        return Decision("inconclusive", f"only {ev.clean_images} clean test photos (need {MIN_CLEAN_IMAGES})")
    holes = ev.per_class.get(HOLE_CLASS, ClassResult())
    total_holes = holes.found + holes.missed
    if total_holes == 0:
        return Decision("inconclusive", "the test photos contain no holes to find")
    problems = []
    if holes.found * MIN_HOLE_RECALL[1] < total_holes * MIN_HOLE_RECALL[0]:
        problems.append(f"holes found {holes.found}/{total_holes} = {100 * holes.found / total_holes:.0f}% (need at least 80%)")
    if ev.clean_alarm_images * MAX_CLEAN_ALARM_RATE[1] > ev.clean_images * MAX_CLEAN_ALARM_RATE[0]:
        problems.append(
            f"false alarms on clean cloth {ev.clean_alarm_images}/{ev.clean_images} = "
            f"{100 * ev.clean_alarm_images / ev.clean_images:.0f}% (allowed at most 20%)"
        )
    if problems:
        return Decision("fallback", "; ".join(problems))
    return Decision("headline", "both kill criteria met")
