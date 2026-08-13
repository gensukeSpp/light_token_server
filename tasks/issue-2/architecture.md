# Issue-2 Architecture Snapshot: Access Token / CRUD to FastAPI

## Purpose
Migrate `app/auth_middleware.py` and `app/routes.py` from Flask to FastAPI per Issue #2. Replace header-based JWT auth with **httpOnly-cookie**-managed access + refresh tokens, and add **`admin`** to the JWT payload.

## Design Overview
- New `app/tokens.py`: JWT issue/verify + cookie helpers (PyJWT HS256, SECRET_KEY from `config`).
- New `app/routers/timetable.py`: FastAPI `APIRouter` porting all `routes.py` endpoints + auth issuance.
- `main.py`: register the router + add `CORSMiddleware(allow_credentials=True)`.
- All DB access goes through `get_db` dependency; the Flask `token_required` decorator becomes `Depends(require_token)`.

## Token & Cookie Design

### Payload (aligns with existing claims, adds `admin`)
```json
{ "user_id": 1001, "group_id": 3, "admin": true, "type": "access", "exp": 1750000000 }
```
- Adds `admin` (`StaffLogin.ADMIN`) alongside existing `user_id` / `group_id`.
- Adds `type` (`"access"` vs `"refresh"`) to reject cross-use.
- Adds `exp` via long-lived defaults: access 24h, refresh 30 days (configurable).

### `app/tokens.py` (new)
```python
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import SECRET_KEY
from .database_base import get_db
from .models import StaffLogin

ALGORITHM = "HS256"
ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
ACCESS_TOKEN_EXPIRE = timedelta(hours=int(__import__("os").getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24")))
REFRESH_TOKEN_EXPIRE = timedelta(days=int(__import__("os").getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30")))


def _encode(payload: dict, expires_delta: timedelta) -> str:
    data = {**payload, "exp": datetime.now(timezone.utc) + expires_delta}
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: int, group_id: int, admin: bool) -> str:
    return _encode({"user_id": user_id, "group_id": group_id, "admin": admin, "type": "access"},
                   ACCESS_TOKEN_EXPIRE)


def create_refresh_token(user_id: int, group_id: int, admin: bool) -> str:
    return _encode({"user_id": user_id, "group_id": group_id, "admin": admin, "type": "refresh"},
                   REFRESH_TOKEN_EXPIRE)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token")


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
    response.set_cookie(ACCESS_COOKIE, access, httponly=True, samesite="lax",
                        max_age=ACCESS_TOKEN_EXPIRE.total_seconds())
    if refresh:
        response.set_cookie(REFRESH_COOKIE, refresh, httponly=True, samesite="lax",
                            max_age=REFRESH_TOKEN_EXPIRE.total_seconds())


def clear_auth_cookies(request: Request, response) -> None:
    response.delete_cookie(ACCESS_COOKIE)
    response.delete_cookie(REFRESH_COOKIE)


def require_token(request: Request, db: Session = Depends(get_db)) -> dict:
    claims = get_token_claims(request, "access")
    user = db.query(StaffLogin).filter(StaffLogin.STAFFID == claims["user_id"]).first()
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    return claims
```
> `require_token` returns the decoded claims so CRUD endpoints read `claims["user_id"]` / `claims["group_id"]` / `claims["admin"]` without a second DB round-trip.

## Router: `app/routers/timetable.py` (new)

### Auth issuance endpoints
```python
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import APP_URL
from ..database_base import get_db
from ..models import StaffLogin, User, Team, EventORM
from ..security import login_required
from ..tokens import (create_access_token, create_refresh_token, set_auth_cookies,
                      get_token_claims, require_token, decode_token,
                      ACCESS_COOKIE, REFRESH_COOKIE)

router = APIRouter()


def get_user_group_id(db: Session, staff_id: int) -> tuple[int, int]:
    u = db.query(User).filter(User.STAFFID == staff_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="user not found")
    return u.STAFFID, u.TEAM_CODE


@router.get("/timetable/auth")
@router.post("/timetable/auth")
def post_access_token(request: Request, db: Session = Depends(get_db),
                      user: StaffLogin = Depends(login_required)):
    staff_id, group_id = get_user_group_id(db, user.STAFFID)
    access = create_access_token(staff_id, group_id, bool(user.ADMIN))
    refresh = create_refresh_token(staff_id, group_id, bool(user.ADMIN))
    response = RedirectResponse(f"{APP_URL}/auth", status_code=303)
    set_auth_cookies(response, access, refresh)
    return response


@router.get("/refresh")
@router.post("/refresh")
def refresh_token(request: Request, db: Session = Depends(get_db)):
    claims = get_token_claims(request, "refresh")
    user = db.query(StaffLogin).filter(StaffLogin.STAFFID == claims["user_id"]).first()
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    access = create_access_token(claims["user_id"], claims["group_id"], bool(user.ADMIN))
    response = RedirectResponse(f"{APP_URL}/auth", status_code=303)
    set_auth_cookies(response, access, None)
    return response
```

### CRUD endpoints (ports of `routes.py`, `@token_required` → `Depends(require_token)`)
| Old (Flask) | New (FastAPI) | Behavior / fix |
| :--- | :--- | :--- |
| `GET/POST /timetable/inquiry` | `@router.get/post("/timetable/inquiry")` | returns `staff_id, group_id, group_name` **+ `admin`** |
| `GET /group/all` | `@router.get("/group/all")` | filter `EventORM.group_id == claims["group_id"]`(旧 filter を修正) |
| `GET/POST /group/users` | `@router.get/post("/group/users")` | `User.TEAM_CODE == claims["group_id"]` |
| `GET /event/all` | `@router.get("/event/all")` | `EventORM` 全件 `to_dict()` |
| `GET/POST /event/user` | `@router.get/post("/event/user")` | `EventORM.staff_id == claims["user_id"]` |
| `GET/POST /group-names` | `@router.get/post("/group-names")` | `Team` 全件 `SHORTNAME` |
| `POST /event/add` | `@router.post("/event/add")` | body from `pydantic`; `convert_strToDate` で日付変換して追加 |
| `POST /event/update/<id>` | `@router.post("/event/update/{id}")` | `summary`/`progress` 更新 |
| `DELETE /event/remove/<id>` | `@router.delete("/event/remove/{id}")` | 削除 |

Example pattern (all protected endpoints share this shape):
```python
@router.get("/timetable/inquiry")
def print_user_inquiry(claims: dict = Depends(require_token), db: Session = Depends(get_db)):
    team = db.get(Team, claims["group_id"])
    return {
        "staff_id": str(claims["user_id"]),
        "group_id": claims["group_id"],
        "group_name": team.SHORTNAME if team else None,
        "admin": claims["admin"],
    }
```

## `main.py` changes
```python
from fastapi.middleware.cors import CORSMiddleware
from .config import ENV, SECRET_KEY, APP_URL
from .routers import login, timetable

app.add_middleware(
    CORSMiddleware,
    allow_origins=[APP_URL, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(login.router)
app.include_router(timetable.router)
```

## `config.py` additions (optional; defaults used otherwise)
```python
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
```

## Files
- New: `app/tokens.py`, `app/routers/timetable.py`
- Modify: `app/main.py`, (optional) `app/config.py`, `tests/conftest.py`
- New tests: `tests/test_tokens.py`, `tests/test_timetable.py`
- Delete (post-verification): `app/routes.py`, `app/auth_middleware.py`
