"""Slows down password guessing.

Five wrong passwords for the same username in 15 minutes locks that username for 15 minutes, whoever is asking and
whether or not the username exists (so the lock reveals nothing). A much higher limit per address stops one machine from
trying many usernames. The state is kept in memory: it resets when the server restarts, and each server process has its own.
Tune with LOGIN_MAX_FAILURES and LOGIN_LOCK_MINUTES in the environment.
"""
import math
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import Request

from app.core.errors import AppError

MAX_TRACKED = 5000


@dataclass
class _Bucket:
    failures: list[float] = field(default_factory=list)
    locked_until: float = 0.0


class LoginGuard:
    def __init__(self, user_limit: int = 5, ip_limit: int = 100, window: float = 900.0, lock: float = 900.0,
                 clock: Callable[[], float] = time.monotonic):
        self.user_limit, self.ip_limit, self.window, self.lock, self.clock = user_limit, ip_limit, window, lock, clock
        self._users: dict[str, _Bucket] = {}
        self._ips: dict[str, _Bucket] = {}
        self._mutex = threading.Lock()

    def check(self, username: str, ip: str) -> None:
        """Raises 429 if this username or this address is locked."""
        now = self.clock()
        with self._mutex:
            remaining = max(
                (b.locked_until - now for b in (self._users.get(username.lower()), self._ips.get(ip)) if b),
                default=0,
            )
        if remaining > 0:
            minutes = max(1, math.ceil(remaining / 60))
            raise AppError("TOO_MANY_ATTEMPTS", f"Too many wrong attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.", status=429)

    def failure(self, username: str, ip: str) -> None:
        now = self.clock()
        with self._mutex:
            for store, key, limit in ((self._users, username.lower(), self.user_limit), (self._ips, ip, self.ip_limit)):
                bucket = store.setdefault(key, _Bucket())
                bucket.failures = [t for t in bucket.failures if now - t < self.window] + [now]
                if len(bucket.failures) >= limit:
                    bucket.locked_until = now + self.lock
                    bucket.failures.clear()
                self._trim(store, now)

    def success(self, username: str) -> None:
        """A correct password clears the count for that username (the address count is left alone)."""
        with self._mutex:
            self._users.pop(username.lower(), None)

    def reset(self) -> None:
        with self._mutex:
            self._users.clear()
            self._ips.clear()

    def _trim(self, store: dict[str, _Bucket], now: float) -> None:
        """Keeps memory bounded: expired entries go first, then the least recently tried unlocked ones. A lock is never dropped."""
        if len(store) <= MAX_TRACKED:
            return
        for key in [k for k, b in store.items() if b.locked_until <= now and not any(now - t < self.window for t in b.failures)]:
            del store[key]
        excess = len(store) - MAX_TRACKED
        if excess > 0:
            unlocked = sorted((k for k, b in store.items() if b.locked_until <= now), key=lambda k: max(store[k].failures, default=0.0))
            for key in unlocked[:excess]:
                del store[key]


guard = LoginGuard(
    user_limit=int(os.getenv("LOGIN_MAX_FAILURES", "5")),
    lock=float(os.getenv("LOGIN_LOCK_MINUTES", "15")) * 60,
)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
