"""The live stream, tested over a real HTTP connection to a real uvicorn server.

TestClient cannot read an endless response, so this starts uvicorn in a thread on a free port,
opens the stream with httpx, and publishes from the test thread, exactly as route handlers
(which run in worker threads) publish in production.
"""
import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from app.core.auth import COOKIE_NAME, create_token
from app.core.events import broadcaster
from app.main import app


@pytest.fixture
def live_server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "uvicorn did not start"
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


def _wait_for_subscribers(n: int, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if len(broadcaster._subs) == n:
            return True
        time.sleep(0.05)
    return False


def test_stream_delivers_events_and_cleans_up_on_disconnect(live_server):
    cookies = {COOKIE_NAME: create_token(1)}
    assert _wait_for_subscribers(0)
    with httpx.stream("GET", f"{live_server}/api/events", cookies=cookies, timeout=10) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert _wait_for_subscribers(1), "stream never subscribed"
        threading.Thread(target=broadcaster.publish, args=("machine.changed", 4)).start()
        data_line = next(line for line in response.iter_lines() if line.startswith("data:"))
        assert json.loads(data_line.removeprefix("data:").strip()) == {"type": "machine.changed", "id": 4}
    assert _wait_for_subscribers(0), "subscription leaked after the client disconnected"


def test_stream_refuses_anonymous_clients(live_server):
    assert httpx.get(f"{live_server}/api/events", timeout=5).status_code == 401
