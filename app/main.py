from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import APP_URL, ENV, SECRET_KEY
from .routers import login, timetable

app = FastAPI(title="light-token-server")

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=(ENV == "production"),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[APP_URL, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(login.router)
app.include_router(timetable.router)


@app.get("/health")
def health():
    return {"status": "ok"}