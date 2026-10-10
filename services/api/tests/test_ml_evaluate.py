import pytest

from ml.evaluate import EvaluationError, score_directory

NAMES = {0: "hole", 1: "stain"}


def make_split(tmp_path, labels: dict[str, str | None]):
    """labels maps an image file name to its label text; None means no label file at all."""
    (tmp_path / "images").mkdir()
    (tmp_path / "labels").mkdir()
    for name, text in labels.items():
        (tmp_path / "images" / name).write_bytes(b"x")
        if text is not None:
            (tmp_path / "labels" / (name.rsplit(".", 1)[0] + ".txt")).write_text(text)
    return tmp_path / "images", tmp_path / "labels"


def hole_at_centre(_path):
    return [("hole", (0.4, 0.4, 0.6, 0.6), 0.9)]


def nothing(_path):
    return []


def test_scores_every_image_with_its_label(tmp_path):
    images, labels = make_split(tmp_path, {"C_hole_1.jpg": "0 0.5 0.5 0.2 0.2\n", "C_clean_1.jpg": ""})
    ev, _ = score_directory(images, labels, NAMES, hole_at_centre)
    assert ev.defective_images == 1 and ev.clean_images == 1
    assert ev.per_class["hole"].found == 1
    assert ev.clean_alarm_images == 1            # the model also fires on the clean photo


def test_a_missing_label_file_is_an_error_not_clean_cloth(tmp_path):
    images, labels = make_split(tmp_path, {"C_hole_1.jpg": "0 0.5 0.5 0.2 0.2\n", "C_oops_2.jpg": None})
    with pytest.raises(EvaluationError, match="C_oops_2.jpg"):
        score_directory(images, labels, NAMES, nothing)


def test_a_bad_label_file_names_the_file(tmp_path):
    images, labels = make_split(tmp_path, {"C_bad_1.jpg": "0 0.5 0.5\n"})
    with pytest.raises(EvaluationError, match="C_bad_1"):
        score_directory(images, labels, NAMES, nothing)


def test_an_empty_test_folder_is_an_error(tmp_path):
    images, labels = make_split(tmp_path, {})
    with pytest.raises(EvaluationError, match="no images"):
        score_directory(images, labels, NAMES, nothing)


def test_non_image_files_are_ignored_and_extensions_are_case_insensitive(tmp_path):
    images, labels = make_split(tmp_path, {"a.JPG": "", "b.png": ""})
    (images / "notes.txt").write_text("hello")
    (images / ".DS_Store").write_bytes(b"x")
    ev, _ = score_directory(images, labels, NAMES, nothing)
    assert ev.clean_images == 2


def test_the_threshold_is_applied(tmp_path):
    images, labels = make_split(tmp_path, {"a.jpg": ""})
    quiet = lambda _p: [("hole", (0.4, 0.4, 0.6, 0.6), 0.1)]
    ev, _ = score_directory(images, labels, NAMES, quiet, conf_thr=0.25)
    assert ev.clean_alarm_images == 0
    ev, _ = score_directory(images, labels, NAMES, quiet, conf_thr=0.05)
    assert ev.clean_alarm_images == 1
