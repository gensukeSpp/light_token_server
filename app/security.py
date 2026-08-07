from fastapi import Depends, Request
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from .database_base import get_db
from .models import StaffLogin


def login_required(request: Request, db: Session = Depends(get_db)) -> StaffLogin:
    staff_id = request.session.get("user_id")
    if staff_id is None:
        raise RedirectResponse("/login", status_code=303)
    user = db.query(StaffLogin).filter(StaffLogin.STAFFID == staff_id).first()
    if user is None:
        raise RedirectResponse("/login", status_code=303)
    return user