from collections import defaultdict
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from atlaslens.api.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from atlaslens.api.deps import get_database
from atlaslens.api.main import app


class _MockDB:
    """Dict-like mock that returns stable AsyncMock per collection."""

    def __init__(self) -> None:
        self._cols: dict[str, AsyncMock] = defaultdict(AsyncMock)

    def __getitem__(self, name: str) -> AsyncMock:
        return self._cols[name]


class TestPasswordHashing:
    def test_hash_and_verify(self) -> None:
        pw = "test-password-123"
        hashed = hash_password(pw)
        assert hashed != pw
        assert verify_password(pw, hashed)

    def test_wrong_password_fails(self) -> None:
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)


class TestJWT:
    def test_create_and_decode(self) -> None:
        token = create_access_token("alice")
        payload = decode_access_token(token)
        assert payload["sub"] == "alice"
        assert "exp" in payload

    def test_expired_token(self) -> None:
        import jwt

        token = create_access_token("alice", expires_minutes=-1)
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token)


def _admin_record() -> dict:  # type: ignore[type-arg]
    return {
        "_id": "admin",
        "username": "admin",
        "password_hash": hash_password("secret123"),
        "created_at": datetime.now(UTC),
        "disabled": False,
    }


class TestAuthRoutes:
    def test_login_success(self) -> None:
        db = _MockDB()
        db["users"].find_one = AsyncMock(
            return_value=_admin_record()
        )

        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/auth/login",
            json={
                "username": "admin",
                "password": "secret123",
            },
        )
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_bad_password(self) -> None:
        db = _MockDB()
        db["users"].find_one = AsyncMock(
            return_value=_admin_record()
        )

        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        app.dependency_overrides.clear()

        assert resp.status_code == 401

    def test_login_user_not_found(self) -> None:
        db = _MockDB()
        db["users"].find_one = AsyncMock(return_value=None)

        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/auth/login",
            json={"username": "ghost", "password": "x"},
        )
        app.dependency_overrides.clear()

        assert resp.status_code == 401

    def test_me_requires_auth(self) -> None:
        db = _MockDB()

        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/auth/me")
        app.dependency_overrides.clear()

        assert resp.status_code in (401, 403)

    def test_me_with_valid_token(self) -> None:
        db = _MockDB()
        db["users"].find_one = AsyncMock(
            return_value=_admin_record()
        )
        token = create_access_token("admin")

        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"
