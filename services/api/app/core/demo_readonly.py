"""A show-piece mode: a login whose name ends in `-demo` can look at everything and change nothing.

Anyone can sign in to the demo logins to explore every screen; every request that would write is refused with a clear message.
Normal logins are not affected. The few POSTs below only ask a question or read something, so a demo login may use them."""
import json

from sqlalchemy import select
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.auth import COOKIE_NAME, read_token
from app.db.models import User
from app.db.session import SessionLocal

DEMO_SUFFIX = "-demo"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# POST routes that write nothing (sign in or out, ask the assistant, run the vision model on a photo, mark the bell as read)
HARMLESS_POSTS = (
    "/api/auth/login",
    "/api/auth/logout",
    "/api/ai/copilot",
    "/api/ai/buyer-assistant",
    "/api/ai/explain-delay/",
    "/api/ai/recall-drafts/",
    "/api/ai/month-summary",
    "/api/qc/analyze",
    "/api/portal/notifications/read",
)
_BODY = json.dumps({"code": "DEMO_READ_ONLY", "message": "This is a read-only demo login, so nothing was changed.", "field": None, "fields": None}).encode()


def _allowed(path: str) -> bool:
    if path.startswith("/api/orders/"):
        return path.endswith("/delay-notice/draft")  # a draft the owner reads; sending the notice is blocked
    return any(path == p or (p.endswith("/") and path.startswith(p)) for p in HARMLESS_POSTS)


def _is_demo_login(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    user_id = read_token(token) if token else None
    if user_id is None:
        return False
    with SessionLocal() as db:
        name = db.scalar(select(User.username).where(User.id == user_id))
    return bool(name) and name.endswith(DEMO_SUFFIX)


class DemoReadOnly:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in SAFE_METHODS and scope["path"].startswith("/api") and not _allowed(scope["path"]):
            if _is_demo_login(Request(scope)):
                await send({"type": "http.response.start", "status": 403, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(_BODY)).encode())]})
                await send({"type": "http.response.body", "body": _BODY})
                return
        await self.app(scope, receive, send)
