"""Fernet encrypt/decrypt for QBO OAuth tokens at rest."""

from cryptography.fernet import Fernet, InvalidToken

import config

_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is None:
        key = config.QBO_ENCRYPTION_KEY
        if not key:
            raise RuntimeError("QBO_ENCRYPTION_KEY is not set in .env")
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt(plaintext):
    """Encrypt a plaintext string, return URL-safe base64 ciphertext string."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext):
    """Decrypt a ciphertext string back to plaintext. Raises on bad key/data."""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError("Failed to decrypt QBO token — check QBO_ENCRYPTION_KEY")
