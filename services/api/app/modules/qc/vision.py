"""Vision QC (B8): run the fine-tuned defect detector on one uploaded photo, and serve the saved model card.

The detector (Ultralytics YOLO) lives in the optional `ml` dependency group and is loaded lazily on the first photo. If it
cannot be loaded the endpoint answers `available=false` and quality checking carries on by hand (spec 9). Everything that
does not need the model (box conversion, the verdict rule, photo reading) is plain Python and unit-tested without it.
"""
import json
import logging
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import get_args

from app.core.enums import DefectType, Verdict
from app.core.validate import check_upload_path, invalid, not_found
from app.modules.qc import schemas as s
from app.modules.uploads.router import upload_root

logger = logging.getLogger(__name__)

MAX_BOXES = 100                                        # the contract's limit on AiSuggestion.boxes
Corners = tuple[float, float, float, float]            # left, top, right, bottom, each a 0-1 fraction of the photo
Detection = tuple[str, Corners, float]                 # defect type, corners, confidence

MODELS_DIR = Path(__file__).resolve().parents[3] / "ml" / "models"
WEIGHTS_PATH = MODELS_DIR / "best.pt"
CARD_PATH = MODELS_DIR / "model_card.json"
IMAGE_SIZE = 640
PREFILTER = 0.05                                       # predict this low, then keep CONFIDENCE and up: how ml.evaluate does it
CONFIDENCE = 0.25
NOTICE = ("Unvalidated first version, trained on public photos only. Nothing found does not mean the cloth is clean: "
          "thread faults and stains are often missed. The inspector decides. See the model card for the measured results.")
BY_HAND = "Inspect by hand."


class ModelUnavailable(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class PhotoUnreadable(Exception):
    pass


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


def _pil_open():
    """PIL's own Image.open. Once Ultralytics is loaded it replaces `Image.open` with a wrapper that, on ANY failure (a
    corrupt file, an oversized one), runs `pip install pi-heif` and then raises ModuleNotFoundError: a network call in the
    middle of a request (the demo may be offline) and the wrong error. We bypass the wrapper and use the original it saved."""
    from PIL import Image
    if Image.open.__module__ == "PIL.Image":
        return Image.open
    return sys.modules["ultralytics.utils.patches"]._image_open


def _read_upright(path: Path):
    """Open a photo the way a browser shows it: the phone's rotation tag applied, three colour channels. The boxes are
    worked out on this upright picture, so they land where the inspector sees the defect."""
    from PIL import Image, ImageOps
    try:
        with _pil_open()(path) as raw:
            return ImageOps.exif_transpose(raw).convert("RGB")
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise PhotoUnreadable() from exc


def _check_class_names(names: dict[int, str]) -> None:
    unknown = sorted(set(names.values()) - set(get_args(DefectType)))
    if unknown:
        raise ModelUnavailable(f"The model reports defect types this system does not know ({', '.join(unknown)}). {BY_HAND}")


def _load_detector() -> Callable[[Path], list[Detection]]:
    if not WEIGHTS_PATH.is_file():
        raise ModelUnavailable(f"The model file is missing (services/api/ml/models/best.pt), so there is no AI suggestion. {BY_HAND}")
    try:
        import torch
        from ultralytics import YOLO
    except ImportError:
        raise ModelUnavailable("The vision libraries are not installed (start the API with `uv run --group ml`), "
                               f"so there is no AI suggestion. {BY_HAND}") from None
    try:
        model = YOLO(str(WEIGHTS_PATH))
    except Exception:
        logger.exception("could not load the vision model from %s", WEIGHTS_PATH)
        raise ModelUnavailable(f"The model file could not be loaded, so there is no AI suggestion. {BY_HAND}") from None
    names = {int(k): v for k, v in model.names.items()}
    _check_class_names(names)
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    def detect(path: Path) -> list[Detection]:
        result = model.predict(_read_upright(path), imgsz=IMAGE_SIZE, conf=PREFILTER, device=device, verbose=False)[0]
        return [(names[int(c)], tuple(map(float, b)), float(p))
                for c, b, p in zip(result.boxes.cls, result.boxes.xyxyn, result.boxes.conf)]

    return detect


_lock = threading.Lock()
_detector: Callable[[Path], list[Detection]] | None = None


def _model_version() -> str:
    try:
        version = json.loads(CARD_PATH.read_text()).get("model_version")
    except (OSError, ValueError, AttributeError):
        version = None
    return version if isinstance(version, str) and version.strip() else WEIGHTS_PATH.stem


def analyze_photo(photo_path: str) -> s.AnalyzeOut:
    """One uploaded photo in, the model's boxes and suggested verdict out. Calls are serialised by one lock (whether the
    detector is safe to call from several threads at once is unverified, so it is not assumed)."""
    global _detector
    path = check_upload_path(photo_path, "photo_path")
    file = upload_root() / path.removeprefix("uploads/")
    if not file.is_file():
        raise not_found("Photo", "photo_path")
    try:
        with _lock:
            if _detector is None:
                _detector = _load_detector()          # a failure is not remembered: fixing the cause works next time
            detections = _detector(file)
    except ModelUnavailable as exc:
        return s.AnalyzeOut(available=False, message=exc.reason, suggestion=None)
    except PhotoUnreadable:
        raise invalid("Could not read this photo; take it again or upload a JPEG or PNG", "photo_path") from None
    except Exception:
        logger.exception("the vision model failed on %s", path)
        return s.AnalyzeOut(available=False, message=f"The model failed on this photo, so there is no AI suggestion. {BY_HAND}",
                            suggestion=None)
    boxes = to_boxes([d for d in detections if d[2] >= CONFIDENCE])
    return s.AnalyzeOut(available=True, message=NOTICE, suggestion=s.AiSuggestion(
        model_version=_model_version(), verdict=suggest_verdict(boxes), boxes=boxes))
