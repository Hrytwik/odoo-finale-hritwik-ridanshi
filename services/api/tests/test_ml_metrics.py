import pytest

from ml.metrics import ImageResult, decide, evaluate, iou

HOLE = "hole"


def box(x, y, w=0.1, h=0.1):  # xyxy, normalised
    return (x, y, x + w, y + h)


def test_iou_identical_disjoint_and_half_overlap():
    assert iou(box(0.1, 0.1), box(0.1, 0.1)) == pytest.approx(1.0)
    assert iou(box(0.0, 0.0), box(0.5, 0.5)) == 0.0
    assert iou((0, 0, 2, 1), (1, 0, 3, 1)) == pytest.approx(1 / 3)


def test_iou_of_degenerate_boxes_is_zero_not_an_error():
    assert iou((0.1, 0.1, 0.1, 0.1), (0.1, 0.1, 0.1, 0.1)) == 0.0


def test_a_found_defect_counts_as_found():
    r = evaluate([ImageResult(truths=[(HOLE, box(0.2, 0.2))], preds=[(HOLE, box(0.21, 0.2), 0.9)])])
    assert r.per_class[HOLE].found == 1 and r.per_class[HOLE].missed == 0 and r.per_class[HOLE].false_alarms == 0
    assert r.per_class[HOLE].recall == 1.0


def test_a_missed_defect_is_missed():
    r = evaluate([ImageResult(truths=[(HOLE, box(0.2, 0.2))], preds=[])])
    assert (r.per_class[HOLE].found, r.per_class[HOLE].missed) == (0, 1)
    assert r.per_class[HOLE].recall == 0.0


def test_a_detection_with_the_wrong_class_is_both_a_miss_and_a_false_alarm():
    r = evaluate([ImageResult(truths=[(HOLE, box(0.2, 0.2))], preds=[("stain", box(0.2, 0.2), 0.9)])])
    assert r.per_class[HOLE].missed == 1
    assert r.per_class["stain"].false_alarms == 1


def test_two_detections_on_one_defect_give_one_hit_and_one_false_alarm():
    preds = [(HOLE, box(0.2, 0.2), 0.9), (HOLE, box(0.2, 0.2), 0.8)]
    r = evaluate([ImageResult(truths=[(HOLE, box(0.2, 0.2))], preds=preds)])
    assert (r.per_class[HOLE].found, r.per_class[HOLE].false_alarms) == (1, 1)


def test_detections_below_the_confidence_threshold_are_ignored():
    r = evaluate([ImageResult(truths=[(HOLE, box(0.2, 0.2))], preds=[(HOLE, box(0.2, 0.2), 0.1)])], conf_thr=0.25)
    assert r.per_class[HOLE].found == 0 and r.per_class[HOLE].missed == 1


def test_a_far_away_detection_is_not_a_match():
    r = evaluate([ImageResult(truths=[(HOLE, box(0.1, 0.1))], preds=[(HOLE, box(0.7, 0.7), 0.9)])])
    assert r.per_class[HOLE].found == 0 and r.per_class[HOLE].false_alarms == 1


def test_clean_image_false_alarm_rate():
    clean_quiet = ImageResult(truths=[], preds=[])
    clean_alarm = ImageResult(truths=[], preds=[(HOLE, box(0.4, 0.4), 0.8)])
    r = evaluate([clean_quiet, clean_quiet, clean_quiet, clean_alarm])
    assert r.clean_images == 4 and r.clean_false_alarm_rate == 0.25


def test_low_confidence_noise_on_clean_cloth_is_not_an_alarm():
    r = evaluate([ImageResult(truths=[], preds=[(HOLE, box(0.4, 0.4), 0.05)])], conf_thr=0.25)
    assert r.clean_false_alarm_rate == 0.0


def test_recall_is_undefined_when_there_is_nothing_to_find():
    r = evaluate([ImageResult(truths=[], preds=[])])
    assert r.per_class == {} and r.clean_false_alarm_rate == 0.0 and r.defective_images == 0


def test_empty_input_is_handled():
    r = evaluate([])
    assert r.clean_false_alarm_rate is None and r.defective_images == 0 and r.clean_images == 0


def _result(defective, clean, hole_found, hole_total, clean_alarms):
    images = []
    for i in range(defective):
        t = [(HOLE, box(0.2, 0.2))] if i < hole_total else []
        p = [(HOLE, box(0.2, 0.2), 0.9)] if i < hole_found else []
        images.append(ImageResult(truths=t or [("stain", box(0.5, 0.5))], preds=p))
    for i in range(clean):
        images.append(ImageResult(truths=[], preds=[(HOLE, box(0.4, 0.4), 0.9)] if i < clean_alarms else []))
    return evaluate(images)


def test_decision_headline_when_both_criteria_met():
    assert decide(_result(30, 30, 25, 30, 5)).verdict == "headline"           # 83% found, 17% false alarms


def test_decision_fallback_when_holes_are_missed():
    d = decide(_result(30, 30, 20, 30, 0))                                    # 67% found
    assert d.verdict == "fallback" and "holes found" in d.reason


def test_decision_fallback_when_false_alarms_are_high():
    d = decide(_result(30, 30, 30, 30, 8))                                    # 27% false alarms
    assert d.verdict == "fallback" and "false alarms" in d.reason


def test_decision_is_inconclusive_with_too_few_test_photos():
    d = decide(_result(10, 30, 10, 10, 0))
    assert d.verdict == "inconclusive" and "defective" in d.reason
    d2 = decide(_result(30, 5, 30, 30, 0))
    assert d2.verdict == "inconclusive" and "clean" in d2.reason


def test_the_boundaries_are_inclusive():
    assert decide(_result(30, 30, 24, 30, 6)).verdict == "headline"           # exactly 80% and exactly 20%


def test_decision_with_no_holes_in_the_test_set_cannot_pass():
    images = [ImageResult(truths=[("stain", box(0.5, 0.5))], preds=[]) for _ in range(30)]
    images += [ImageResult(truths=[], preds=[]) for _ in range(30)]
    assert decide(evaluate(images)).verdict == "inconclusive"
