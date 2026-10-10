import io

import pytest

from app.config import settings

JPEG = b"\xff\xd8\xff fake"
PNG = b"\x89PNG\r\n\x1a\n fake"
WEBP = b"RIFF\x00\x00\x00\x00WEBP fake"


@pytest.fixture(autouse=True)
def tmp_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


def test_upload_and_fetch_jpeg(client, login_as, tmp_uploads):
    login_as("qc")
    r = client.post("/api/uploads", files={"file": ("roll.jpg", io.BytesIO(JPEG), "image/jpeg")})
    assert r.status_code == 200
    body = r.json()
    assert body["path"].startswith("uploads/") and body["url"].startswith("/api/uploads/")
    assert client.get(body["url"]).content == JPEG


@pytest.mark.parametrize("content_type,data,ext", [("image/png", PNG, ".png"), ("image/webp", WEBP, ".webp")])
def test_png_and_webp_accepted(client, login_as, content_type, data, ext):
    login_as("qc")
    r = client.post("/api/uploads", files={"file": ("a", io.BytesIO(data), content_type)})
    assert r.status_code == 200 and r.json()["url"].endswith(ext)


def test_upload_requires_login(client):
    r = client.post("/api/uploads", files={"file": ("a.jpg", io.BytesIO(b"x"), "image/jpeg")})
    assert r.status_code == 401


def test_download_requires_login(client):
    assert client.get("/api/uploads/" + "a" * 32 + ".jpg").status_code == 401


def test_non_image_rejected(client, login_as):
    login_as("qc")
    r = client.post("/api/uploads", files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")})
    assert r.status_code == 422 and r.json()["code"] == "UNSUPPORTED_FILE"


def test_declared_image_with_other_content_rejected(client, login_as):
    login_as("qc")
    r = client.post("/api/uploads", files={"file": ("a.jpg", io.BytesIO(b"<html>hi</html>"), "image/jpeg")})
    assert r.status_code == 422 and r.json()["code"] == "UNSUPPORTED_FILE"


def test_png_bytes_declared_as_jpeg_rejected(client, login_as):
    login_as("qc")
    r = client.post("/api/uploads", files={"file": ("a.jpg", io.BytesIO(PNG), "image/jpeg")})
    assert r.status_code == 422


def test_empty_file_rejected(client, login_as):
    login_as("qc")
    r = client.post("/api/uploads", files={"file": ("a.jpg", io.BytesIO(b""), "image/jpeg")})
    assert r.status_code == 422 and r.json()["code"] == "EMPTY_FILE"


def test_oversized_file_rejected(client, login_as):
    login_as("qc")
    big = io.BytesIO(JPEG + b"\0" * (10 * 1024 * 1024))
    r = client.post("/api/uploads", files={"file": ("a.jpg", big, "image/jpeg")})
    assert r.status_code == 413 and r.json()["code"] == "FILE_TOO_LARGE"


def test_exactly_10_mb_is_accepted(client, login_as):
    login_as("qc")
    data = JPEG + b"\0" * (10 * 1024 * 1024 - len(JPEG))
    r = client.post("/api/uploads", files={"file": ("a.jpg", io.BytesIO(data), "image/jpeg")})
    assert r.status_code == 200


@pytest.mark.parametrize("name", ["../secret.jpg", "..%2Fsecret.jpg", "abc.jpg", "x" * 32 + ".exe"])
def test_bad_names_are_404(client, login_as, name):
    login_as("qc")
    assert client.get(f"/api/uploads/{name}").status_code == 404


def test_valid_looking_name_that_does_not_exist_is_404(client, login_as):
    login_as("qc")
    assert client.get("/api/uploads/" + "0" * 32 + ".jpg").status_code == 404
