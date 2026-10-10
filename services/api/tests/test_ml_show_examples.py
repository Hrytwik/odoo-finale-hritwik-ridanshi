"""The photo picker behind `python -m ml.show_examples` (the part that needs no model)."""
from ml.show_examples import Row, describe, pick_examples


def row(name, found, missed, kinds=1, false_alarms=0, truths=None, preds=None):
    return Row(name, truths or [], preds or [], found, missed, false_alarms, kinds)


def test_it_picks_the_first_photo_with_two_kinds_all_found_and_the_first_with_a_miss():
    rows = [row("a", 1, 0, kinds=1), row("b", 2, 0, kinds=2), row("c", 3, 1), row("d", 2, 2, kinds=2)]
    assert [(title, r.name) for title, r in pick_examples(rows)] == [("ALL FOUND", "b"), ("SOMETHING MISSED", "c")]


def test_a_kind_with_no_fitting_photo_is_left_out():
    assert pick_examples([row("a", 1, 0, kinds=1)]) == []                    # no photo with two kinds, none with a miss
    assert pick_examples([row("x", 0, 2)]) == []                              # all missed: nothing was found to show
    assert [(t, r.name) for t, r in pick_examples([row("y", 1, 1)])] == [("SOMETHING MISSED", "y")]


def test_no_photos_gives_nothing():
    assert pick_examples([]) == []


def test_describe_says_what_the_file_line_means_and_marks_false_alarms():
    truths = [("thread_fault", (0.0, 0.43, 0.18, 0.57))]
    preds = [("thread_fault", (0.0, 0.43, 0.17, 0.57), 0.49), ("thread_fault", (0.0, 0.43, 0.12, 0.54), 0.28),
             ("hole", (0.6, 0.6, 0.9, 0.9), 0.40)]
    text = "\n".join(describe(truths, preds, ["2 0.09 0.50 0.17 0.14"]))
    assert "2 0.09 0.50 0.17 0.14" in text and "thread_fault" in text
    assert text.count("matches a real defect") == 1                           # a real defect can be found only once
    assert text.count("FALSE ALARM") == 2                                      # the duplicate and the hole that is not there
    assert text.index("confidence=0.49") < text.index("confidence=0.40") < text.index("confidence=0.28")   # best guess first
