"""B8 Task 2: photos are read the way a browser shows them (rotation applied); unreadable files are refused cleanly."""
import pytest

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

try:                       # in production Ultralytics is always loaded before the first photo is read: test in that state
    import ultralytics  # noqa: F401
except ImportError:
    ultralytics = None

from app.modules.qc.vision import ModelUnavailable, PhotoUnreadable, _check_class_names, _read_upright  # noqa: E402


def save_jpeg(path, size=(40, 20), orientation=None):
    img = Image.new("RGB", size, "white")
    exif = img.getexif()
    if orientation is not None:
        exif[0x0112] = orientation
    img.save(path, "JPEG", exif=exif)
    return path


def test_a_normal_photo_keeps_its_size(tmp_path):
    assert _read_upright(save_jpeg(tmp_path / "a.jpg")).size == (40, 20)


@pytest.mark.parametrize("orientation,size", [(1, (40, 20)), (3, (40, 20)), (6, (20, 40)), (8, (20, 40))])
def test_the_phones_rotation_tag_is_applied(tmp_path, orientation, size):
    assert _read_upright(save_jpeg(tmp_path / "a.jpg", orientation=orientation)).size == size


def test_the_result_has_three_colour_channels(tmp_path):
    Image.new("L", (10, 10)).save(tmp_path / "g.png")
    assert _read_upright(tmp_path / "g.png").mode == "RGB"


def test_bytes_that_are_not_an_image_are_refused(tmp_path):
    (tmp_path / "x.jpg").write_bytes(b"\xff\xd8\xff this is not really a picture")
    with pytest.raises(PhotoUnreadable):
        _read_upright(tmp_path / "x.jpg")


def test_a_cut_off_file_is_refused(tmp_path):
    good = save_jpeg(tmp_path / "a.jpg", size=(200, 200)).read_bytes()
    (tmp_path / "cut.jpg").write_bytes(good[: len(good) // 2])
    with pytest.raises(PhotoUnreadable):
        _read_upright(tmp_path / "cut.jpg")


def test_a_decompression_bomb_is_refused(tmp_path, monkeypatch):
    save_jpeg(tmp_path / "big.jpg", size=(200, 200))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)           # 200 x 200 is far above twice this limit
    with pytest.raises(PhotoUnreadable):
        _read_upright(tmp_path / "big.jpg")


def test_class_names_the_contract_knows_are_accepted():
    _check_class_names({0: "hole", 1: "stain", 2: "thread_fault"})


def test_class_names_the_contract_does_not_know_make_the_model_unavailable():
    with pytest.raises(ModelUnavailable) as err:
        _check_class_names({0: "hole", 1: "banana"})
    assert "banana" in err.value.reason


def test_a_bad_photo_never_makes_ultralytics_try_to_install_a_package(tmp_path, monkeypatch):
    """Once Ultralytics is loaded it replaces PIL's Image.open with a version that, on ANY failure, runs
    `pip install pi-heif` and then raises ModuleNotFoundError. Reading must bypass it: no install attempt (the
    demo may be offline), and a clean 'unreadable photo' answer."""
    if ultralytics is None:
        pytest.skip("Ultralytics is not installed")
    from ultralytics.utils import checks

    def forbidden(*args, **kwargs):
        raise AssertionError("tried to install a package while reading a photo")
    monkeypatch.setattr(checks, "check_requirements", forbidden)
    assert Image.open.__module__ != "PIL.Image"                   # the Ultralytics replacement really is in place
    (tmp_path / "x.jpg").write_bytes(b"\xff\xd8\xff this is not really a picture")
    with pytest.raises(PhotoUnreadable):
        _read_upright(tmp_path / "x.jpg")
