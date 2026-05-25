import logging

from cryptography.fernet import Fernet, InvalidToken

from atlaslens.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None
_initialized = False


def _get_fernet() -> Fernet | None:
    global _fernet, _initialized
    if _initialized:
        return _fernet
    _initialized = True
    key = settings.encryption_key
    if not key:
        return None
    try:
        _fernet = Fernet(key.encode())
    except Exception:
        logger.warning(
            "invalid encryption_key — field encryption disabled"
        )
    return _fernet


def encrypt_field(value: str) -> str:
    f = _get_fernet()
    if f is None:
        return value
    return f.encrypt(value.encode()).decode()


def decrypt_field(value: str) -> str:
    f = _get_fernet()
    if f is None:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except InvalidToken:
        return value
