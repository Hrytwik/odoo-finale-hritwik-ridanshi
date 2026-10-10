"""B8 Task 1: the detector's corner boxes become the contract's top-left-plus-size boxes; the verdict rule."""
from itertools import product

import pytest

from app.modules.qc.vision import MAX_BOXES, suggest_verdict, to_boxes


def det(cls="hole", corners=(0.2, 0.3, 0.6, 0.7), conf=0.9):
    return (cls, corners, conf)


def test_corners_become_top_left_plus_size():
    [b] = to_boxes([det(corners=(0.2, 0.3, 0.6, 0.7))])
    assert (b.x, b.y) == (0.2, 0.3)
    assert b.w == pytest.approx(0.4) and b.h == pytest.approx(0.4)
    assert b.defect_type == "hole" and b.confidence == 0.9


def test_a_box_that_is_not_square_keeps_width_and_height_apart():
    [b] = to_boxes([det(corners=(0.1, 0.2, 0.5, 0.3))])          # wide and short
    assert b.w == pytest.approx(0.4) and b.h == pytest.approx(0.1)


def test_the_whole_photo():
    [b] = to_boxes([det(corners=(0.0, 0.0, 1.0, 1.0))])
    assert (b.x, b.y, b.w, b.h) == (0.0, 0.0, 1.0, 1.0)


def test_a_box_touching_the_right_and_bottom_edges():
    [b] = to_boxes([det(corners=(0.9, 0.8, 1.0, 1.0))])
    assert b.x + b.w == pytest.approx(1.0) and b.y + b.h == pytest.approx(1.0)


def test_a_tiny_box_is_kept():
    [b] = to_boxes([det(corners=(0.5, 0.5, 0.501, 0.501))])
    assert 0 < b.w < 0.01 and 0 < b.h < 0.01


def test_swapped_corners_give_the_same_box():
    assert to_boxes([det(corners=(0.6, 0.7, 0.2, 0.3))]) == to_boxes([det(corners=(0.2, 0.3, 0.6, 0.7))])


def test_a_box_sticking_out_of_the_photo_is_clamped():
    [b] = to_boxes([det(corners=(-0.05, 0.2, 1.05, 0.5))])
    assert (b.x, b.w) == (0.0, 1.0)


@pytest.mark.parametrize("corners", [(1.0, 0.2, 1.0, 0.5), (0.2, 0.5, 0.6, 0.5), (1.2, 0.2, 1.5, 0.5), (-0.5, 0.2, -0.1, 0.5)])
def test_a_box_with_no_area_inside_the_photo_is_dropped(corners):
    assert to_boxes([det(corners=corners)]) == []


def test_every_combination_of_edge_values_stays_inside_the_photo():
    values = [-0.1, 0.0, 0.3, 0.5, 1.0, 1.1]
    for corners in product(values, repeat=4):
        for b in to_boxes([det(corners=corners)]):
            assert 0 <= b.x <= 1 and 0 <= b.y <= 1
            assert 0 < b.w <= 1 and 0 < b.h <= 1
            assert b.x + b.w <= 1 + 1e-9 and b.y + b.h <= 1 + 1e-9


def test_highest_confidence_first_and_at_most_100():
    detections = [det(conf=0.25 + i / 1000) for i in range(150)]
    boxes = to_boxes(detections)
    assert len(boxes) == MAX_BOXES == 100
    confidences = [b.confidence for b in boxes]
    assert confidences == sorted(confidences, reverse=True)
    assert confidences[0] == pytest.approx(0.25 + 149 / 1000) and confidences[-1] == pytest.approx(0.25 + 50 / 1000)


def test_dropped_degenerate_boxes_do_not_use_up_the_100():
    junk = [det(corners=(1.0, 0.2, 1.0, 0.5), conf=0.99) for _ in range(10)]
    real = [det(conf=0.5 + i / 1000) for i in range(100)]
    assert len(to_boxes(junk + real)) == 100


def test_no_detections_no_boxes():
    assert to_boxes([]) == []


def test_verdict_is_pass_without_boxes_and_rework_with_any_and_never_reject():
    assert suggest_verdict([]) == "pass"
    one = to_boxes([det()])
    assert suggest_verdict(one) == "rework"
    assert suggest_verdict(to_boxes([det(conf=0.25 + i / 1000) for i in range(100)])) == "rework"
