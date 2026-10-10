"""Response headers that close off a few easy attacks. Plain ASGI, so streaming responses (the live event stream) are untouched."""
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADERS = {
    b"x-content-type-options": b"nosniff",   # the browser must not guess a different type than the one we send
    b"x-frame-options": b"DENY",             # no other site may show this one in a frame (clickjacking)
    b"referrer-policy": b"same-origin",      # no addresses leak to other sites
}


class SecurityHeaders:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        no_store = scope["path"].startswith("/api/auth")

        async def add(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in HEADERS]
                headers += list(HEADERS.items())
                if no_store:
                    # login, logout and "who am I" answers must never be kept by a browser or a proxy
                    headers = [(k, v) for k, v in headers if k.lower() != b"cache-control"] + [(b"cache-control", b"no-store")]
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, add)
