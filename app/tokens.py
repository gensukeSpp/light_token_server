from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import (
    ACCESS_TOKEN_EXPIRE_HOURS,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
)
from .database_base import get_db
from .models import StaffLogin

ALGORITHM = "HS256"

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

ACCESS_TOKEN_EXPIRE = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
REFRESH_TOKEN_EXPIRE = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)


def _encode(payload: dict, expires_delta: timedelta) -> str:
    data = {**payload, "exp": datetime.now(timezone.utc) + expires_delta}
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: int, group_id: int, admin: bool) -> str:
    return _encode(
        {"user_id": user_id, "group_id": group_id, "admin": admin, "type": "access"},
        ACCESS_TOKEN_EXPIRE,
    )


def create_refresh_token(user_id: int, group_id: int, admin: bool) -> str:
    return _encode(
        {"user_id": user_id, "group_id": group_id, "admin": admin, "type": "refresh"},
        REFRESH_TOKEN_EXPIRE,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="token expired") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="invalid token") from e


def get_token_claims(request: Request, expected_type: str) -> dict:
    cookie = ACCESS_COOKIE if expected_type == "access" else REFRESH_COOKIE
    token = request.cookies.get(cookie)
    if not token:
        raise HTTPException(status_code=401, detail="missing token")
    claims = decode_token(token)
    if claims.get("type") != expected_type:
        raise HTTPException(status_code=401, detail="wrong token type")
    return claims


def set_auth_cookies(response, access: str, refresh: str | None) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        httponly=True,
        samesite="lax",
        max_age=int(ACCESS_TOKEN_EXPIRE.total_seconds()),
    )
    if refresh:
        response.set_cookie(
            REFRESH_COOKIE,
            refresh,
            httponly=True,
            samesite="lax",
            max_age=int(REFRESH_TOKEN_EXPIRE.total_seconds()),
        )


def require_token(request: Request, db: Session = Depends(get_db)) -> dict:
    """httpOnly アクセストークン Cookie を検証し claims を返す認可依存。"""
    claims = get_token_claims(request, "access")
    user = db.query(StaffLogin).filter(StaffLogin.STAFFID == claims["user_id"]).first()
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    return claims
