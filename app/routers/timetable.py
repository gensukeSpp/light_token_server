import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..config import APP_URL
from ..database_base import get_db
from ..models import StaffLogin, Team, User, EventORM
from ..schemas import EventCreate, EventUpdate, EventDateUpdate
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
    try:
        return datetime.strptime(replaced, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        # 形式が異なる入力（datetime-local 等）で 500 になるのを防ぐ。
        # 期待形式: 'YYYY-MM-DDTHH:MM:SS[.fff]Z'
        raise HTTPException(
            status_code=422,
            detail=f"Invalid datetime format: {str_date!r}; expected 'YYYY-MM-DDTHH:MM:SS[.fff]Z'",
        )


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
    # 旧 Flask の契約: アクセストークンを URL クエリ ?token= で渡し、/auth で受ける。
    # httpOnly Cookie も併せてセットする（両対応）。
    print(APP_URL)
    response = RedirectResponse(f"{APP_URL}/auth?token={access}", status_code=303)
    set_auth_cookies(response, access, refresh)
    return response


@router.get("/refresh")
@router.post("/refresh")
def refresh_token(request: Request, db: Session = Depends(get_db)):
    # 旧 Flask 契約: 呼び出し側 (time-table-to-line) はアクセストークンを Bearer で送って
    # /refresh を叩く。access / refresh どちらの type も受理する (type 検証を緩和)。
    claims = get_token_claims(request, {"access", "refresh"})
    user = db.query(StaffLogin).filter(StaffLogin.STAFFID == claims.get("user_id")).first()
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    access = create_access_token(claims.get("user_id"), claims.get("group_id"), bool(user.ADMIN))
    # 旧 Flask の契約: 新しいアクセストークンの文字列を body で返す。
    # Cookie にも再セットする（両対応）。
    response = JSONResponse({"access_token": access})
    set_auth_cookies(response, access, None)
    return response


@router.get("/timetable/inquiry")
@router.post("/timetable/inquiry")
def print_user_inquiry(claims: dict = Depends(require_token), db: Session = Depends(get_db)):
    team = db.get(Team, claims["group_id"])
    return {
        "staff_id": str(claims.get("user_id")),
        "group_id": claims.get("group_id"),
        "group_name": team.SHORTNAME if team else None,
        "admin": claims.get("admin"),
    }


@router.get("/group/all")
def get_team_events(claims: dict = Depends(require_token), db: Session = Depends(get_db)):
    events = db.query(EventORM).filter(EventORM.group_id == claims.get("group_id")).all()
    return [event.to_dict() for event in events]


@router.get("/group/users")
@router.post("/group/users")
def get_team_member(claims: dict = Depends(require_token), db: Session = Depends(get_db)):
    members = db.query(User).filter(User.TEAM_CODE == claims.get("group_id")).all()
    return [{"staff_id": m.STAFFID, "family_kana": m.FKANA, "last_kana": m.LKANA} for m in members]


@router.get("/event/all")
def get_all_event(claims: dict = Depends(require_token), db: Session = Depends(get_db)):
    events = db.query(EventORM).all()
    return [event.to_dict() for event in events]


@router.get("/event/user")
@router.post("/event/user")
def get_user_event(claims: dict = Depends(require_token), db: Session = Depends(get_db)):
    events = db.query(EventORM).filter(EventORM.staff_id == claims.get("user_id")).all()
    return [event.to_dict() for event in events]


@router.get("/group-names")
@router.post("/group-names")
def get_team_name(claims: dict = Depends(require_token), db: Session = Depends(get_db)):
    teams = db.query(Team).all()
    return [t.SHORTNAME for t in teams]


@router.post("/event/add", status_code=201)
def append_event_item(
    body: EventCreate,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    print(f"Insert 前: {body.start_time}")
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


@router.post("/date/update")
def update_event_dates(
    body: EventDateUpdate,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    # Timeline/Calendar のドラッグ&ドロップによる日時移動・リサイズの一括保存。
    # フロント (useUpdateDateListMutation) が { data: [{id, start_time, end_time}] } を送る。
    # 更新対象イベントは、作成者本人のみ権限を持つ（他メンバーのイベントは触らせない）。
    updated: list[EventORM] = []
    for item in body.data:
        target = db.query(EventORM).filter(EventORM.id == item.id).first()
        if target is None:
            raise HTTPException(status_code=404, detail=f"event not found: {item.id}")
        if target.staff_id != claims.get("user_id"):
            raise HTTPException(
                status_code=403,
                detail=f"not allowed to update other member's event: {item.id}",
            )
        target.start_time = convert_str_to_date(item.start_time)
        target.end_time = convert_str_to_date(item.end_time)
        updated.append(target)
    db.commit()
    return [event.to_dict() for event in updated]


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
