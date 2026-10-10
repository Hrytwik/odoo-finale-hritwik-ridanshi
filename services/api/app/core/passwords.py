"""Password rules: how strong a new password must be, how the stored hash is kept current, and a hash to check against
when the username does not exist (so a wrong username takes as long to refuse as a wrong password)."""
import hashlib
import re

import bcrypt

# bcrypt work factor. Each +1 doubles the time a guess takes; 12 is about a quarter of a second today.
BCRYPT_COST = 12
MIN_LENGTH = 8
MAX_BYTES = 72  # bcrypt ignores everything after 72 bytes, so a longer password is refused rather than silently cut

_COMMON = frozenset({
    "password", "password1", "password123", "12345678", "123456789", "1234567890", "qwertyui", "qwerty123",
    "iloveyou", "admin123", "letmein1", "welcome1", "abc12345", "11111111", "00000000",
})

# checked against when the username is unknown, so the work done does not reveal whether the account exists
DUMMY_HASH = bcrypt.hashpw(b"not-the-password-of-anyone", bcrypt.gensalt(rounds=BCRYPT_COST)).decode()


def check_new_password(password: str, username: str) -> str | None:
    """Why this password is not allowed, in words for the person choosing it, or None if it is fine."""
    if len(password) < MIN_LENGTH:
        return f"Use at least {MIN_LENGTH} characters"
    if len(password.encode()) > MAX_BYTES:
        return f"Use at most {MAX_BYTES} bytes (about {MAX_BYTES} letters and numbers)"
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Use both letters and at least one number"
    if password.lower() in _COMMON:
        return "That password is too common. Choose another"
    if len(username) >= 3 and username.lower() in password.lower():
        return "Do not put your username in your password"
    return None


def bcrypt_cost(hashed: str) -> int | None:
    """The work factor a stored hash was made with ($2b$12$... is 12), or None if it is not a bcrypt hash."""
    match = re.match(r"^\$2[abxy]\$(\d{2})\$", hashed)
    return int(match.group(1)) if match else None


def needs_rehash(hashed: str) -> bool:
    """True when the stored hash is weaker than today's setting. It is replaced on the next successful login."""
    cost = bcrypt_cost(hashed)
    return cost is not None and cost < BCRYPT_COST


def fingerprint(hashed: str) -> str:
    """A short value that changes whenever the password does. Sessions carry it, so changing a password ends the old sessions."""
    return hashlib.sha256(hashed.encode()).hexdigest()[:16]
