from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from atlaslens.api.auth import create_access_token, verify_password
from atlaslens.api.deps import get_current_user, get_database

router = APIRouter(prefix="/auth", tags=["auth"])

DB = Annotated[
    AsyncIOMotorDatabase, Depends(get_database)  # type: ignore[type-arg]
]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login")
async def login(body: LoginRequest, db: DB) -> TokenResponse:
    user = await db["users"].find_one({"username": body.username})
    if not user or not verify_password(
        body.password, user["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if user.get("disabled"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )
    token = create_access_token(user["username"])
    return TokenResponse(access_token=token)


@router.get("/me")
async def me(user: CurrentUser) -> dict[str, Any]:
    return {
        "username": user["username"],
        "created_at": user.get("created_at"),
    }


@router.post("/logout")
async def logout(user: CurrentUser) -> dict[str, str]:
    return {"status": "ok"}
