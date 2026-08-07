# AGENTS.md — light_token_server

## Overview
Backend for login + access-token handling for the `time-table-to-line` app
(`cd ../time-table-to-line`): login, token issue/discard/reissue, httpOnly session
cookie, a link page, and CRUD endpoints, restricted to a limited user set.
Requirement: `requirement-02.md` (read it before changing behavior). The spec's goal
is migrating the current Flask/MySQL base to **FastAPI / PostgreSQL / Pydantic /
htmx / uv / pytest**. Its steps 1–7 are not strictly ordered and refactoring anytime
is allowed — the stated "目的" (goal) is what matters, not a checklist.

## Current state (IMPORTANT — repo is NOT yet FastAPI)
- `app/` code is still **Flask** (`flask`, `flask_login`, `flask_cors`,
  `flask_sqlalchemy`, `flask_wtf`, `werkzeug`, `jwt`). Migration to FastAPI is the task.
- **No dependency manifest**: no pyproject.toml / requirements.txt / uv.lock / setup.py.
  Deps exist only via imports and the list in requirement-02.md.
- `tests/` is empty. `.github/` has **no workflows** — only `agents/pr-review.md`
  (an AI prompt, not CI). So there are **no build/test/lint commands to run yet**.
- **No `app/__init__.py`** → `from app import app, db` cannot resolve; the package is
  currently not importable/runnable as a unit.

## Dev environment (target, per requirement-02)
- Python 3.13.11; dependency management via **`uv`**.
- Target stack: FastAPI, uvicorn, SQLAlchemy, Alembic, Jinja2, httpx, Pydantic, pytest.
- DB: **PostgreSQL** (from MySQL); Render + Neon planned. Templates: **htmx** (no Bootstrap).

## Build & test
- Nothing is runnable today (no manifest). Intended once scaffolded with uv:
  - deps: `uv add fastapi uvicorn sqlalchemy alembic jinja2 httpx pydantic pytest`
  - tests: `uv run pytest` (tests go under `tests/`)
- Add to shell history: re-derive commands from the real manifest once it exists;
  don't assume a test command exists before pyproject/uv.lock does.

## Conventions (observed in `app/`)
- Models in `models.py`: legacy UPPERCASE columns (STAFFID, TEAM_CODE, …), tables
  `M_STAFFINFO`, `M_TEAM`, `M_LOGGININFO`, `T_TIMELINE_EVENT`; `Base` comes from
  `database_base.py`. Keep the old DB schema shape ("旧アプリの形式").
- Passwords: `werkzeug` `generate_password_hash` / `check_password_hash`
  (`StaffLogin.check_password`).
- Auth: JWT **HS256** (`jwt` lib); `issue_token()` → payload `{user_id, group_id}`;
  `token_required` decorator verifies (returns `(auth_user, extension)`).
- CORS origins: `os.getenv("CLOUD_TIMETABLE4")` + `http://localhost:5173`. DB URL built
  from env `DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME` (dotenv).
- UI copy is Japanese; templates in `app/templates/` (`base.html`, `login.html`,
  `logout.html`).
- `EventORM.to_dict()` emits ISO `"%Y-%m-%dT%H:%M:%S.000Z"` — preserve that format.
- Existing code has many stray `print()` and commented-out blocks; requirement-02 says
  remove stray prints and inappropriate comments during migration.

## Pitfalls
- **Do NOT run DB migrations** — the PostgreSQL migration (step 5 of requirement-02)
  is done by the user personally ("ここは私が行う"). Prepare Alembic, leave the run to them.
- `.venv/` and `.env` are gitignored — do not read or commit `.env` (DB creds + secrets).
- Dead leftover references in current code to drop/clean during migration:
  - `login.py` imports `from .forms import LoginForm`, but the file is `form.py`.
  - `url_for("select_links")` and `render_template("logout_mes.html")` in `login.py`
    point at routes/templates that don't exist; `select_links` is to be removed.
- No `app/__init__.py` → package won't import until one exists (the FastAPI restructure
  should add it).
- If `../time-table-to-line` exists on the machine, match the token shape and link URL
  to how that app consumes them — informational, not a build dependency.
