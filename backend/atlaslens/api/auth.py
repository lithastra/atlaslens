from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from atlaslens.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode(), bcrypt.gensalt()
    ).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(
    subject: str,
    expires_minutes: int | None = None,
) -> str:
    expire = datetime.now(UTC) + timedelta(
        minutes=expires_minutes or settings.jwt_expire_minutes
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    return jwt.encode(
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
