import pytest

from ml.yolo_labels import LabelError, parse_labels

NAMES = {0: "hole", 1: "stain", 2: "thread_fault"}


def test_parses_a_normalised_box_into_corner_coordinates():
    (cls, box), = parse_labels("0 0.5 0.5 0.2 0.1\n", NAMES)
    assert cls == "hole"
    assert box == pytest.approx((0.4, 0.45, 0.6, 0.55))


def test_several_boxes_and_blank_lines():
    got = parse_labels("0 0.5 0.5 0.2 0.2\n\n  \n1 0.1 0.1 0.1 0.1\n", NAMES)
    assert [c for c, _ in got] == ["hole", "stain"]


def test_an_empty_file_means_clean_cloth():
    assert parse_labels("", NAMES) == []
    assert parse_labels("\n\n", NAMES) == []


def test_a_missing_file_is_treated_as_clean_only_when_asked():
    assert parse_labels(None, NAMES) == []


@pytest.mark.parametrize("line", ["0 0.5 0.5 0.2", "0 0.5 0.5 0.2 0.1 0.9", "hole 0.5 0.5 0.2 0.1", "0 a b c d"])
def test_malformed_lines_raise_a_clear_error(line):
    with pytest.raises(LabelError, match="line 1"):
        parse_labels(line, NAMES)


def test_unknown_class_id_raises():
    with pytest.raises(LabelError, match="class 7"):
        parse_labels("7 0.5 0.5 0.2 0.1", NAMES)


@pytest.mark.parametrize("line", ["0 1.2 0.5 0.2 0.1", "0 0.5 0.5 0 0.1", "0 0.5 0.5 0.2 -0.1", "0 -0.1 0.5 0.2 0.1"])
def test_out_of_range_values_raise(line):
    with pytest.raises(LabelError):
        parse_labels(line, NAMES)


def test_a_box_that_pokes_out_of_the_image_is_clipped_not_rejected():
    (_, box), = parse_labels("0 0.95 0.5 0.2 0.2", NAMES)
    assert box[2] == 1.0 and box[0] == pytest.approx(0.85)


def test_error_messages_name_the_line_number():
    with pytest.raises(LabelError, match="line 3"):
        parse_labels("0 0.5 0.5 0.2 0.2\n0 0.5 0.5 0.2 0.2\nbroken", NAMES)
