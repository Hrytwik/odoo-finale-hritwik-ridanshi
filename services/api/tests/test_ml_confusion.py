"""B8 Task 3: the confusion matrix uses the very matching the per-class scores use, so the two always agree."""
import random

import pytest

from ml.metrics import ImageResult, confusion_matrix, evaluate

CLASSES = ["hole", "stain", "thread_fault"]
CLEAN = 3
BOX = (0.4, 0.4, 0.6, 0.6)
OFF = (0.0, 0.0, 0.1, 0.1)


def img(truths=(), preds=()):
    return ImageResult(truths=list(truths), preds=list(preds))


def test_a_found_defect_is_on_the_diagonal():
    m = confusion_matrix([img([("hole", BOX)], [("hole", BOX, 0.9)])], CLASSES)
    assert m[0][0] == 1 and sum(map(sum, m)) == 1


def test_a_missed_defect_is_in_the_clean_column_of_its_row():
    m = confusion_matrix([img([("stain", BOX)])], CLASSES)
    assert m[1][CLEAN] == 1 and sum(map(sum, m)) == 1


def test_a_false_alarm_is_in_the_clean_row_of_its_column():
    m = confusion_matrix([img(preds=[("hole", BOX, 0.9)])], CLASSES)
    assert m[CLEAN][0] == 1 and sum(map(sum, m)) == 1


def test_a_clean_photo_with_no_guess_is_the_clean_clean_cell():
    m = confusion_matrix([img()], CLASSES)
    assert m[CLEAN][CLEAN] == 1 and sum(map(sum, m)) == 1


def test_a_clean_photo_with_a_weak_guess_below_the_line_still_counts_as_clean():
    m = confusion_matrix([img(preds=[("hole", BOX, 0.2)])], CLASSES)
    assert m[CLEAN][CLEAN] == 1 and m[CLEAN][0] == 0


def test_a_defective_photo_with_no_guess_is_not_a_clean_clean_cell():
    m = confusion_matrix([img([("hole", BOX)])], CLASSES)
    assert m[CLEAN][CLEAN] == 0


def test_the_right_place_with_the_wrong_name_is_a_miss_plus_a_false_alarm():
    m = confusion_matrix([img([("hole", BOX)], [("stain", BOX, 0.9)])], CLASSES)
    assert m[0][CLEAN] == 1 and m[CLEAN][1] == 1 and m[0][1] == 0


def test_a_guess_far_from_the_defect_is_a_miss_plus_a_false_alarm():
    m = confusion_matrix([img([("hole", BOX)], [("hole", OFF, 0.9)])], CLASSES)
    assert m[0][CLEAN] == 1 and m[CLEAN][0] == 1


def test_one_real_defect_can_be_found_only_once():
    m = confusion_matrix([img([("hole", BOX)], [("hole", BOX, 0.9), ("hole", BOX, 0.8)])], CLASSES)
    assert m[0][0] == 1 and m[CLEAN][0] == 1


def test_an_unknown_class_is_an_error_not_a_silent_skip():
    with pytest.raises(ValueError, match="banana"):
        confusion_matrix([img([("banana", BOX)])], CLASSES)


def random_image(rng):
    def box():
        x, y = rng.random() * 0.7, rng.random() * 0.7
        return (x, y, x + 0.1 + rng.random() * 0.2, y + 0.1 + rng.random() * 0.2)
    truths = [(rng.choice(CLASSES), box()) for _ in range(rng.randint(0, 3))]
    preds = [(rng.choice(CLASSES), box(), rng.random()) for _ in range(rng.randint(0, 4))]
    preds += [(c, b, rng.random()) for c, b in truths if rng.random() < 0.6]             # some guesses sit on real defects
    return img(truths, preds)


def test_rows_and_columns_add_up_to_the_per_class_scores_on_random_photos():
    rng = random.Random(7)
    images = [random_image(rng) for _ in range(300)]
    ev = evaluate(images)
    m = confusion_matrix(images, CLASSES)
    for i, name in enumerate(CLASSES):
        score = ev.per_class.get(name)
        found, missed, false_alarms = (score.found, score.missed, score.false_alarms) if score else (0, 0, 0)
        assert m[i][i] == found
        assert sum(m[i]) == found + missed                      # row: everything really there
        assert sum(row[i] for row in m) == found + false_alarms  # column: everything the model said
    assert ev.defective_images + ev.clean_images == 300
    assert m[CLEAN][CLEAN] + ev.clean_alarm_images == ev.clean_images
