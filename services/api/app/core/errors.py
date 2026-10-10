from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class ErrorBody(BaseModel):
    code: str
    message: str
    field: str | None = None
    fields: dict[str, str] | None = None


class AppError(Exception):
    def __init__(self, code: str, message: str, *, field: str | None = None, status: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.status = status


# constraint name -> (code, field, message). Modules add their own entries.
KNOWN_CONSTRAINTS: dict[str, tuple[str, str | None, str]] = {}


def _friendly(msg: str) -> str:
    return msg.removeprefix("Value error, ")


def map_integrity_error(exc: IntegrityError) -> AppError:
    diag = getattr(exc.orig, "diag", None)
    name = getattr(diag, "constraint_name", None) or ""
    table = getattr(diag, "table_name", None) or ""
    sqlstate = getattr(exc.orig, "sqlstate", None)
    if name in KNOWN_CONSTRAINTS:
        code, field, message = KNOWN_CONSTRAINTS[name]
        return AppError(code, message, field=field)
    if sqlstate == "23505":
        field = name.removeprefix(f"uq_{table}_") or None
        return AppError("DUPLICATE", "This already exists", field=field)
    if sqlstate == "23503":
        return AppError("NOT_FOUND", "A referenced record does not exist", status=404)
    if sqlstate == "23502":
        return AppError("REQUIRED", "A required value is missing",
                        field=getattr(diag, "column_name", None), status=422)
    return AppError("INVALID_VALUE", f"Value not allowed ({name or 'constraint'})", status=422)


def commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise map_integrity_error(exc) from exc


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        body = ErrorBody(code=exc.code, message=exc.message, field=exc.field)
        return JSONResponse(status_code=exc.status, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for err in exc.errors():
            parts = [str(p) for p in err["loc"] if p not in ("body", "query", "path")]
            fields.setdefault(".".join(parts) or "request", _friendly(err["msg"]))
        first_field, first_msg = next(iter(fields.items()))
        body = ErrorBody(code="VALIDATION_ERROR", message=first_msg, field=first_field, fields=fields)
        return JSONResponse(status_code=422, content=body.model_dump())
