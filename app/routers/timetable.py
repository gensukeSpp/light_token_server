import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import APP_URL
from ..database_base import get_db
from ..models import StaffLogin, Team, User, EventORM
from ..schemas import EventCreate, EventUpdate
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


def convert_str_to_date(str_date: str) -> datetime:
    regex_data = re.sub(r"\.\d{3}Z", "", str_date)
    replaced = regex_data.replace("T", " ")
    return datetime.strptime(replaced, "%Y-%m-%d %H:%M:%S")


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
def print_user_inquiry(
    claims: dict = Depends(require_token), db: Session = Depends(get_db)
):
    team = db.get(Team, claims["group_id"])
    return {
        "staff_id": str(claims["user_id"]),
        "group_id": claims["group_id"],
        "group_name": team.SHORTNAME if team else None,
        "admin": claims["admin"],
    }


@router.get("/group/all")
def get_team_events(
    claims: dict = Depends(require_token), db: Session = Depends(get_db)
):
    events = (
        db.query(EventORM).filter(EventORM.group_id == claims["group_id"]).all()
    )
    return [event.to_dict() for event in events]


@router.get("/group/users")
@router.post("/group/users")
def get_team_member(
    claims: dict = Depends(require_token), db: Session = Depends(get_db)
):
    members = (
        db.query(User).filter(User.TEAM_CODE == claims["group_id"]).all()
    )
    return [
        {"staff_id": m.STAFFID, "family_kana": m.FKANA, "last_kana": m.LKANA}
        for m in members
    ]


@router.get("/event/all")
def get_all_event(
    claims: dict = Depends(require_token), db: Session = Depends(get_db)
):
    events = db.query(EventORM).all()
    return [event.to_dict() for event in events]


@router.get("/event/user")
@router.post("/event/user")
def get_user_event(
    claims: dict = Depends(require_token), db: Session = Depends(get_db)
):
    events = (
        db.query(EventORM)
        .filter(EventORM.staff_id == claims["user_id"])
        .all()
    )
    return [event.to_dict() for event in events]


@router.get("/group-names")
@router.post("/group-names")
def get_team_name(
    claims: dict = Depends(require_token), db: Session = Depends(get_db)
):
    teams = db.query(Team).all()
    return [t.SHORTNAME for t in teams]


@router.post("/event/add", status_code=201)
def append_event_item(
    body: EventCreate,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    event = EventORM(
        staff_id=body.staff_id,
        group_id=body.group,
        start_time=convert_str_to_date(body.start_time),
        end_time=convert_str_to_date(body.end_time),
        title=body.title,
        summary=body.summary,
        progress=body.progress,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event.to_dict()


@router.post("/event/update/{event_id}")
def update_event_item(
    event_id: int,
    body: EventUpdate,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    target = db.query(EventORM).filter(EventORM.id == event_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="event not found")
    if body.summary is not None:
        target.summary = body.summary
    if body.progress is not None:
        target.progress = body.progress
    db.commit()
    return target.to_dict()


@router.delete("/event/remove/{event_id}")
def remove_event_item(
    event_id: int,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    target = db.query(EventORM).filter(EventORM.id == event_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="event not found")
    db.delete(target)
    db.commit()
    return {"deleted": event_id}