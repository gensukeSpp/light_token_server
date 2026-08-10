# AGENTS.md — light_token_server

## Overview
Backend for login + access-token handling for the `time-table-to-line` app
(`cd ../time-table-to-line`): login, token issue/discard/reissue, httpOnly session
cookie, a link page, and CRUD endpoints, restricted to a limited user set.
Requirement: `requirement-02.md` (read it before changing behavior). The spec's goal
is migrating the current Flask/MySQL base to **FastAPI / PostgreSQL / Pydantic /
htmx / uv / pytest**. Its steps 1–7 are not strictly ordered and refactoring anytime
is allowed — the stated "目的" (goal) is what matters, not a checklist.

## Current state (partially migrated)
- **Done:** dependency manifest (`pyproject.toml`, `uv.lock`, `.python-version` pin 3.13),
  the **login flow**, and the **access-token / CRUD endpoints are all FastAPI** (Flask fully removed).
- **FastAPI modules:** `app/main.py` (FastAPI app + `SessionMiddleware` + `CORSMiddleware` +
  `include_router`), `app/routers/login.py` (`/login` GET/POST, `/logout`, `/` link page),
  `app/routers/timetable.py` (token issuance `/timetable/auth`, `/refresh`, and CRUD),
  `app/tokens.py` (JWT access/refresh + httpOnly cookie helpers + `require_token`),
  `app/schemas.py` (Pydantic), `app/security.py` (`login_required` via `get_db`),
  `app/config.py` (env settings), `app/database_base.py` (`engine`/`SessionLocal`/`Base`/`get_db`).
- **Templates** are plain HTML (Bootstrap removed): `base.html`, `login.html`, `index.html`.
  `logout.html` is a dead leftover from the old Flask app.
- **Access tokens:** JWT HS256 (`PyJWT`) in `app/tokens.py`, issued as **httpOnly cookies**
  (`access_token` + `refresh_token`). Payload = `{user_id, group_id, admin, type, exp}`,
  where `admin` comes from `StaffLogin.ADMIN`. Long expiry for a limited org (defaults
  access 24h / refresh 30 days, env-tunable via `ACCESS_TOKEN_EXPIRE_HOURS` /
  `REFRESH_TOKEN_EXPIRE_DAYS`). Protected endpoints use `Depends(require_token)`.
- `app/models.py` keeps the legacy schema shape (UPPERCASE columns, tables `M_STAFFINFO`
  `M_TEAM` `M_LOGGININFO` `T_TIMELINE_EVENT`).
- **DB is still MySQL** until the user migrates it to PostgreSQL. Tests do NOT need a real DB.

## IMPORTANT: activate the venv before uv/pytest
- The project is **not a pre-activated venv**. Before ANY `uv` or `pytest`/`uvicorn` command, run:
  ```bash
  source .venv/bin/activate
  ```
  Then use `uv ...` / `uv run pytest ...` / `uvicorn app.main:app`. (The venv already has
  FastAPI + testing deps installed via uv.)

## Dev environment
- Python **3.13** (pinned in `.python-version`); dependency management via **`uv`**.
- Stack: FastAPI, uvicorn, SQLAlchemy, Alembic, Jinja2, httpx, Pydantic, PyJWT,
  psycopg(binary), python-dotenv, python-multipart, itsdangerous (session), werkzeug (password).
- DB: **PostgreSQL** (from MySQL); Render + Neon planned. Templates: **htmx** (no Bootstrap).

## Build & test
- Tests: `uv run pytest` (tests live under `tests/`; `test_health.py`, `test_login.py`,
  `test_tokens.py`, `test_timetable.py`).
  pytest config lives in `pyproject.toml` (`testpaths`, `pythonpath = ["."]`).
- Run the server: `uvicorn app.main:app` → `/health` returns `{"status":"ok"}`.

## Conventions
- Models keep the legacy schema; `Base` comes from `database_base.py`.
  `EventORM.to_dict()` emits ISO `"%Y-%m-%dT%H:%M:%S.000Z"` — preserve it.
- Passwords: `werkzeug` `generate_password_hash` / `check_password_hash`
  (`StaffLogin.check_password`). Keep werkzeug so existing hashes verify.
- Auth (login): httpOnly session cookie via `SessionMiddleware` (`SECRET_KEY` from env).
- Auth (access token): JWT HS256 (`PyJWT`) lives in `app/tokens.py`. Access + refresh are
  set as httpOnly cookies (`access_token`/`refresh_token`). Protected endpoints use
  `Depends(require_token)` (reads the `access_token` cookie); `/refresh` re-issues via
  `get_token_claims(request, "refresh")`. Payload keys: `user_id`, `group_id`, `admin`, `type`, `exp`.
- DB access in FastAPI code **must** go through the `get_db` dependency
  (`db: Session = Depends(get_db)`), never a bare `SessionLocal()` — that's what lets tests
  override with SQLite.
- Forms: Pydantic schema + `Annotated[LoginForm, Form()]` (needs `python-multipart`).
- CORS origins: `os.getenv("CLOUD_TIMETABLE4")` + `http://localhost:5173`. DB URL built from
  env `DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME` (or `DATABASE_URL`).
- UI copy is Japanese; templates in `app/templates/`.
- Starlette 1.4.1: `TemplateResponse(request, name, {…})` is request-first, and you must
  `raise HTTPException(303, headers={"Location": …})` rather than `raise RedirectResponse`.
  See the `flask-to-fastapi-migration` skill for details.

## Pitfalls
- **Do NOT run DB migrations** — the PostgreSQL migration (step 5 of requirement-02)
  is done by the user personally ("ここは私が行う"). Prepare Alembic, leave the run to them.
- `.venv/` and `.env` are gitignored — do not read or commit `.env` (DB creds + secrets).
- `routes.py` / `auth_middleware.py` were **removed** (Issue #2) — do not re-add Flask code
  or Flask imports under `app/`; keep `main.py` on the FastAPI routers only.
- Don't `raise RedirectResponse(...)` (Starlette 1.4.1 rejects it); use `HTTPException` 303.
- Tests use SQLite in-memory with `poolclass=StaticPool` + `connect_args={"check_same_thread":
  False}` (TestClient runs the app in a worker thread; without StaticPool the tables vanish).
- If `../time-table-to-line` exists on the machine, match the token shape and link URL
  to how that app consumes them — informational, not a build dependency.
