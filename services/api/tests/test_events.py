import asyncio
import threading
import time

from app.core.events import Broadcaster


def test_publish_from_worker_thread_reaches_subscriber():
    async def scenario():
        b = Broadcaster()
        q = b.subscribe()
        waiter = asyncio.ensure_future(q.get())
        await asyncio.sleep(0.05)  # the loop is now idle, blocked waiting for a message

        def publish_later():
            time.sleep(0.2)  # publish only once the loop is definitely asleep in select()
            b.publish("machine.changed", 4)

        threading.Thread(target=publish_later).start()
        msg = await asyncio.wait_for(waiter, timeout=2)
        b.unsubscribe(q)
        return msg

    assert asyncio.run(scenario()) == '{"type": "machine.changed", "id": 4}'


def test_full_queue_drops_instead_of_blocking():
    async def scenario():
        b = Broadcaster(max_queue=1)
        q = b.subscribe()
        b.publish("a")
        b.publish("b")
        await asyncio.sleep(0.05)
        return q.qsize()

    assert asyncio.run(scenario()) == 1


def test_events_requires_login(client):
    assert client.get("/api/events").status_code == 401
