from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import APP_URL
from ..database_base import get_db
from ..models import StaffLogin, User
from ..security import login_required
from ..tokens import (
    create_access_token,
    create_refresh_token,
    get_token_claims,
    require_token,
    set_auth_cookies,
)

router = APIRouter()


def get_user_group_id(db: Session, staff_id: int) -> tuple[int, int]:
    u = db.query(User).filter(User.STAFFID == staff_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="user not found")
    return u.STAFFID, u.TEAM_CODE


@router.get("/timetable/auth")
@router.post("/timetable/auth")
def post_access_token(
    request: Request,
    db: Session = Depends(get_db),
    user: StaffLogin = Depends(login_required),
):
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
    user = (
        db.query(StaffLogin).filter(StaffLogin.STAFFID == claims["user_id"]).first()
    )
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    access = create_access_token(
        claims["user_id"], claims["group_id"], bool(user.ADMIN)
    )
    response = RedirectResponse(f"{APP_URL}/auth", status_code=303)
    set_auth_cookies(response, access, None)
    return response


@router.get("/timetable/inquiry")
@router.post("/timetable/inquiry")
def print_user_inquiry(claims: dict = Depends(require_token)):
    return {
        "staff_id": str(claims["user_id"]),
        "group_id": claims["group_id"],
        "admin": claims["admin"],
    }