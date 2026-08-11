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
    print(f"Signing token with secret (first 5): {SECRET_KEY[:5]}...")
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


def _bearer_token(request: Request) -> str | None:
    """Authorization: Bearer <token> ヘッダーから token を取り出す。無ければ None。"""
    auth = request.headers.get("Authorization")
    if not auth:
        print("No Authorization header found")
        return None
    parts = auth.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        print(f"Invalid Authorization header format: {auth}")
        return None
    token = parts[1].strip()
    print(f"Found token in header: {token[:10]}...")
    return token


def get_token_claims(request: Request, expected_type: str | set[str]) -> dict:
    """アクセス検証用 claims を返す。

    Authorization: Bearer *** ヘッダーを優先し、無ければ httpOnly Cookie で受ける。
    どちらも無効/欠如なら 401。expected_type は単一の type 文字列か、許可する type の
    集合で渡す (/refresh では旧契約のアクセストークンとリフレッシュトークンの両方を受理するため
    {"access", "refresh"} を渡す)。
    """
    allowed = {expected_type} if isinstance(expected_type, str) else set(expected_type)
    token = _bearer_token(request)
    if token is None:
        # cookie フォールバック: refresh を許可する構成では refresh を優先し、次に access。
        print("No bearer token found, checking cookies")
        if "refresh" in allowed:
            token = request.cookies.get(REFRESH_COOKIE)
        if token is None and "access" in allowed:
            token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        print("No token found")
        raise HTTPException(status_code=401, detail="missing token")
    
    claims = decode_token(token)
    print(f"Decoded claims: {claims}")
    
    if claims.get("type") not in allowed:
        print(f"Wrong token type: {claims.get('type')}, expected: {allowed}")
        raise HTTPException(status_code=401, detail="wrong token type")
    
    print("Token validated successfully")
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
