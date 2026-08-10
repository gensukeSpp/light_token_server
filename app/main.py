from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from .config import ENV, SECRET_KEY
from .routers import login, timetable

app = FastAPI(title="light-token-server")

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=(ENV == "production"),
)
app.include_router(login.router)
app.include_router(timetable.router)


@app.get("/health")
def health():
    return {"status": "ok"}