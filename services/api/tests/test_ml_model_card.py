"""B8 Task 4: the card file has exactly the shape the API serves."""
from datetime import UTC, datetime

from app.modules.qc.schemas import ModelCard
from ml.metrics import ImageResult, confusion_matrix, evaluate
from ml.model_card import DATASETS, card_dict

CLASSES = ["hole", "stain", "thread_fault"]
BOX = (0.4, 0.4, 0.6, 0.6)
WHEN = datetime(2026, 10, 10, 9, 30, tzinfo=UTC)


def build(images):
    return card_dict(evaluate(images), confusion_matrix(images, CLASSES), CLASSES,
                     model_version="yolo-test", trained_at=WHEN, datasets=DATASETS)


def images():
    return [ImageResult([("hole", BOX)], [("hole", BOX, 0.9)]), ImageResult([("stain", BOX)], [])]


def test_the_card_passes_the_api_schema():
    card = ModelCard(available=True, **build(images()))
    assert card.model_version == "yolo-test" and card.trained_at == WHEN
    assert (card.test_defective, card.test_clean) == (2, 0)


def test_every_class_is_listed_in_order_even_one_with_no_photos():
    card = build(images())
    assert [p["defect_type"] for p in card["per_class"]] == CLASSES
    thread = card["per_class"][2]
    assert (thread["found"], thread["missed"], thread["false_alarms"]) == (0, 0, 0)
    assert thread["precision"] is None and thread["recall"] is None


def test_with_no_clean_photos_the_false_alarm_rate_is_null_not_zero():
    assert build(images())["clean_false_alarm_rate"] is None


def test_with_clean_photos_it_is_the_measured_rate():
    imgs = images() + [ImageResult([], [("hole", BOX, 0.9)]), ImageResult([], [])]
    assert build(imgs)["clean_false_alarm_rate"] == 0.5


def test_the_matrix_labels_end_with_clean_and_the_matrix_is_square():
    card = build(images())
    assert card["confusion_labels"] == [*CLASSES, "clean"]
    assert all(len(row) == 4 for row in card["confusion_matrix"]) and len(card["confusion_matrix"]) == 4


def test_the_datasets_credit_the_roboflow_set_with_its_licence():
    [d] = DATASETS
    assert d["licence"] == "CC BY 4.0" and d["url"].startswith("https://universe.roboflow.com/")
