import asyncio
import json
import threading


def _offer(queue: asyncio.Queue, message: str) -> None:
    if not queue.full():
        queue.put_nowait(message)


class Broadcaster:
    """Fan-out of small change events to every open live stream.

    publish() may be called from any thread (sync route handlers run in a thread pool);
    each message is handed to the subscriber's own event loop with call_soon_threadsafe.
    """

    def __init__(self, max_queue: int = 100) -> None:
        self._max_queue = max_queue
        self._subs: dict[asyncio.Queue, asyncio.AbstractEventLoop] = {}
        self._lock = threading.Lock()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        with self._lock:
            self._subs[queue] = asyncio.get_running_loop()
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._lock:
            self._subs.pop(queue, None)

    def publish(self, event_type: str, id: int | str | None = None) -> None:
        message = json.dumps({"type": event_type, "id": id})
        with self._lock:
            targets = list(self._subs.items())
        for queue, loop in targets:
            try:
                loop.call_soon_threadsafe(_offer, queue, message)
            except RuntimeError:
                self.unsubscribe(queue)


broadcaster = Broadcaster()
