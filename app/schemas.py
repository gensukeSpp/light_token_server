from pydantic import BaseModel


class LoginForm(BaseModel):
    STAFFID: int
    PASSWORD: str
    remember_me: bool = False


class EventCreate(BaseModel):
    staff_id: int
    group: int
    start_time: str
    end_time: str
    title: str
    summary: str | None = None
    progress: str | None = None


class EventUpdate(BaseModel):
    summary: str | None = None
    progress: str | None = None