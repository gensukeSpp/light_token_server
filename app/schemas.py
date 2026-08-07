from pydantic import BaseModel


class LoginForm(BaseModel):
    STAFFID: int
    PASSWORD: str
    remember_me: bool = False