import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings
from app.core.auth import current_user, session_user_id
from app.core.errors import AppError

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_BYTES = 10 * 1024 * 1024
NAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")


class UploadOut(BaseModel):
    path: str
    url: str


def upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def looks_like(ext: str, data: bytes) -> bool:
    """Check the file's own first bytes, not just the type the browser claimed."""
    if ext == ".jpg":
        return data.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


@router.post("", response_model=UploadOut, dependencies=[Depends(current_user)])
async def upload(file: UploadFile) -> UploadOut:
    ext = ALLOWED.get(file.content_type or "")
    if ext is None:
        raise AppError("UNSUPPORTED_FILE", "Only JPEG, PNG or WebP photos", field="file", status=422)
    data = await file.read(MAX_BYTES + 1)
    if not data:
        raise AppError("EMPTY_FILE", "The file is empty", field="file", status=422)
    if len(data) > MAX_BYTES:
        raise AppError("FILE_TOO_LARGE", "Photos must be 10 MB or smaller", field="file", status=413)
    if not looks_like(ext, data):
        raise AppError("UNSUPPORTED_FILE", "That file is not a valid photo", field="file", status=422)
    name = f"{uuid.uuid4().hex}{ext}"
    (upload_root() / name).write_bytes(data)
    return UploadOut(path=f"uploads/{name}", url=f"/api/uploads/{name}")


@router.get("/{name}", response_class=FileResponse, dependencies=[Depends(session_user_id)])
def download(name: str) -> FileResponse:
    if not NAME_RE.fullmatch(name):
        raise AppError("NOT_FOUND", "File not found", status=404)
    path = upload_root() / name
    if not path.is_file():
        raise AppError("NOT_FOUND", "File not found", status=404)
    return FileResponse(path)
