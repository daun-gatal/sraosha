"""Symmetric encryption helpers for storing credentials at rest.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the ``cryptography`` library.
The key is sourced from ``settings.ENCRYPTION_KEY``.  If empty, a
deterministic dev-only key is derived so the application still starts
without explicit configuration.
"""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from sraosha.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet  # noqa: PLW0603
    if _fernet is not None:
        return _fernet

    raw_key = settings.ENCRYPTION_KEY
    if not raw_key:
        raw_key = "sraosha-dev-key-not-for-production"
        logger.warning("ENCRYPTION_KEY is not set; using insecure dev-only key")

    digest = hashlib.sha256(raw_key.encode()).digest()
    key = base64.urlsafe_b64encode(digest[:32])
    _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string and return a URL-safe base64 token."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet token back to plaintext.  Raises ValueError on failure."""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt credential — key mismatch or corrupted data") from exc
