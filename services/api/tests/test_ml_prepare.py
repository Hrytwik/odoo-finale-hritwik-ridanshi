import pytest

from ml.prepare_data import OURS, ROBOFLOW_TO_OURS, PrepareError, build_dataset, remap_label_text


def test_our_class_order_is_fixed():
    assert OURS == ["hole", "stain", "thread_fault"]


def test_roboflow_classes_are_mapped_by_meaning_not_by_number():
    # roboflow ids: 0 color, 1 hole, 2 thread  ->  ours: 0 hole, 1 stain, 2 thread_fault
    assert ROBOFLOW_TO_OURS == {0: 1, 1: 0, 2: 2}


def test_remap_changes_only_the_class_id():
    text = "0 0.5 0.4 0.2 0.1\n1 0.3 0.3 0.05 0.05\n2 0.9 0.9 0.1 0.1\n"
    assert remap_label_text(text, ROBOFLOW_TO_OURS) == "1 0.5 0.4 0.2 0.1\n0 0.3 0.3 0.05 0.05\n2 0.9 0.9 0.1 0.1\n"


def test_remap_keeps_an_empty_file_empty():
    assert remap_label_text("", ROBOFLOW_TO_OURS) == ""
    assert remap_label_text("\n\n", ROBOFLOW_TO_OURS) == ""


def test_remap_refuses_an_unknown_class_instead_of_guessing():
    with pytest.raises(PrepareError, match="class 7"):
        remap_label_text("7 0.5 0.5 0.1 0.1\n", ROBOFLOW_TO_OURS)


def test_remap_refuses_malformed_lines():
    with pytest.raises(PrepareError, match="line 2"):
        remap_label_text("0 0.5 0.5 0.1 0.1\n0 0.5\n", ROBOFLOW_TO_OURS)


def make_source(root, split, items):
    (root / split / "images").mkdir(parents=True)
    (root / split / "labels").mkdir(parents=True)
    for stem, label in items.items():
        (root / split / "images" / f"{stem}.jpg").write_bytes(b"img-" + stem.encode())
        if label is not None:
            (root / split / "labels" / f"{stem}.txt").write_text(label)


def test_build_combines_sources_and_remaps_only_the_public_one(tmp_path):
    pub, own, out = tmp_path / "pub", tmp_path / "own", tmp_path / "out"
    make_source(pub, "train", {"a": "1 0.5 0.5 0.1 0.1\n"})          # roboflow hole -> our 0
    make_source(pub, "valid", {"v": "0 0.5 0.5 0.1 0.1\n"})          # roboflow color -> our stain (1)
    make_source(own, "train", {"A_hole_001": "0 0.5 0.5 0.1 0.1\n", "A_clean_002": ""})
    stats = build_dataset(out, public=pub, own=own)
    assert (out / "train" / "labels" / "public_a.txt").read_text() == "0 0.5 0.5 0.1 0.1\n"
    assert (out / "val" / "labels" / "public_v.txt").read_text() == "1 0.5 0.5 0.1 0.1\n"
    assert (out / "train" / "labels" / "own_A_hole_001.txt").read_text() == "0 0.5 0.5 0.1 0.1\n"
    assert (out / "train" / "labels" / "own_A_clean_002.txt").read_text() == ""      # clean cloth stays clean
    assert stats["train_images"] >= 3
    yaml_text = (out / "data.yaml").read_text()
    assert "0: hole" in yaml_text and "1: stain" in yaml_text and "2: thread_fault" in yaml_text


def test_build_without_public_data_is_variant_a(tmp_path):
    own, out = tmp_path / "own", tmp_path / "out"
    make_source(own, "train", {f"A_hole_{i:03}": "0 0.5 0.5 0.1 0.1\n" for i in range(20)})
    build_dataset(out, public=None, own=own)
    assert not any(p.name.startswith("public_") for p in (out / "train" / "images").iterdir())
    assert len(list((out / "val" / "images").iterdir())) >= 1            # own photos supply a validation set


def test_validation_split_of_own_photos_is_stable_and_never_the_test_set(tmp_path):
    own = tmp_path / "own"
    make_source(own, "train", {f"A_hole_{i:03}": "0 0.5 0.5 0.1 0.1\n" for i in range(40)})
    make_source(own, "test", {"C_hole_001": "0 0.5 0.5 0.1 0.1\n"})
    out1, out2 = tmp_path / "o1", tmp_path / "o2"
    build_dataset(out1, public=None, own=own)
    build_dataset(out2, public=None, own=own)
    names = lambda d: sorted(p.name for p in (d / "val" / "images").iterdir())
    assert names(out1) == names(out2)
    for out in (out1, out2):
        for split in ("train", "val"):
            assert not any("C_hole" in p.name for p in (out / split / "images").iterdir())


def test_missing_label_file_is_an_error_not_clean_cloth(tmp_path):
    own, out = tmp_path / "own", tmp_path / "out"
    make_source(own, "train", {"A_hole_001": "0 0.5 0.5 0.1 0.1\n", "A_oops_002": None})
    with pytest.raises(PrepareError, match="A_oops_002"):
        build_dataset(out, public=None, own=own)


def test_building_twice_does_not_mix_old_files(tmp_path):
    own, out = tmp_path / "own", tmp_path / "out"
    make_source(own, "train", {f"A_hole_{i:03}": "0 0.5 0.5 0.1 0.1\n" for i in range(12)})
    build_dataset(out, public=None, own=own)
    for kind, ext in (("images", "jpg"), ("labels", "txt")):                 # a photo is removed, another added
        (own / "train" / kind / f"A_hole_000.{ext}").unlink()
    (own / "train" / "images" / "A_hole_new.jpg").write_bytes(b"x")
    (own / "train" / "labels" / "A_hole_new.txt").write_text("0 0.5 0.5 0.1 0.1\n")
    build_dataset(out, public=None, own=own)
    left = [p.name for s in ("train", "val") for p in (out / s / "images").iterdir()]
    assert "own_A_hole_000.jpg" not in left and "own_A_hole_new.jpg" in left


def test_a_tiny_own_set_without_public_data_is_refused_clearly(tmp_path):
    own = tmp_path / "own"
    make_source(own, "train", {"A_hole_001": "0 0.5 0.5 0.1 0.1\n"})
    with pytest.raises(PrepareError, match="validation"):
        build_dataset(tmp_path / "out", public=None, own=own)


def test_the_public_test_split_is_exported_remapped_and_kept_apart(tmp_path):
    pub, out = tmp_path / "pub", tmp_path / "out"
    make_source(pub, "train", {"a": "1 0.5 0.5 0.1 0.1\n"})
    make_source(pub, "valid", {"v": "0 0.5 0.5 0.1 0.1\n"})
    make_source(pub, "test", {"t": "2 0.5 0.5 0.1 0.1\n", "u": "0 0.2 0.2 0.1 0.1\n"})
    stats = build_dataset(out, public=pub, own=None)
    assert stats["test_public_images"] == 2
    assert (out / "test_public" / "labels" / "public_t.txt").read_text() == "2 0.5 0.5 0.1 0.1\n"
    assert (out / "test_public" / "labels" / "public_u.txt").read_text() == "1 0.2 0.2 0.1 0.1\n"
    assert not any("_t.jpg" in p.name or "_u.jpg" in p.name for s in ("train", "val") for p in (out / s / "images").iterdir())


def test_a_public_folder_without_a_test_split_is_fine(tmp_path):
    pub = tmp_path / "pub"
    make_source(pub, "train", {"a": "1 0.5 0.5 0.1 0.1\n"})
    make_source(pub, "valid", {"v": "0 0.5 0.5 0.1 0.1\n"})
    assert build_dataset(tmp_path / "out", public=pub, own=None)["test_public_images"] == 0
