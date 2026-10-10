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
