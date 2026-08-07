from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from ..database_base import get_db
from ..models import StaffLogin
from ..schemas import LoginForm
from ..security import login_required

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    if request.session.get("user_id") is not None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request, "login.html", {"error": None}
    )


@router.post("/login")
def do_login(
    request: Request,
    form: Annotated[LoginForm, Form()],
    db: Session = Depends(get_db),
):
    user = (
        db.query(StaffLogin).filter(StaffLogin.STAFFID == form.STAFFID).first()
    )
    if user is None or not user.check_password(form.PASSWORD):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "ユーザ名かパスワードが違います"},
            status_code=400,
        )
    request.session["user_id"] = user.STAFFID
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def do_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/")
def index(request: Request, user: StaffLogin = Depends(login_required)):
    return templates.TemplateResponse(
        request, "index.html", {"user": user}
    )