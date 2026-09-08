from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import APP_URL, ENABLE_MILESTONE_SCHEDULER, ENV, SECRET_KEY
from .routers import login, timetable
from .scheduler import create_milestone_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if ENABLE_MILESTONE_SCHEDULER:
        scheduler = create_milestone_scheduler()
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown()


app = FastAPI(title="light-token-server", lifespan=lifespan)

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
