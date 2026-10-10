"""Encrypts the language-model API key before it is stored. The key is never sent back to the browser."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    # LLM_KEY_SECRET from .env; the login secret is the fallback so a fresh checkout still works
    secret = settings.llm_key_secret or settings.jwt_secret
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def encrypt_key(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_key(token: str) -> str | None:
    """The key, or None if it cannot be read (the secret changed): the owner then enters it again."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None
