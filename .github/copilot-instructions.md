# Copilot instructions — light-token-server

## Build, test, and lint commands

The project targets Python 3.13 and uses `uv`. The virtual environment is not
activated automatically:

```bash
source .venv/bin/activate
```

Run the full test suite:

```bash
source .venv/bin/activate && uv run pytest
```

Run one test module or one test:

```bash
source .venv/bin/activate && uv run pytest tests/test_milestone.py
source .venv/bin/activate && uv run pytest tests/test_login.py::test_login_success_sets_session
```

Run the development server:

```bash
source .venv/bin/activate && uvicorn app.main:app --reload
```

`pyproject.toml` configures pytest to use `tests/` and adds the repository root
to `PYTHONPATH`. There is no configured project lint command or lint tool.

## High-level architecture

- `app/main.py` creates the FastAPI app, installs `SessionMiddleware` and
  credentialed CORS, includes the login and timetable routers, exposes
  `/health`, and starts the optional milestone scheduler in the FastAPI
  lifespan.
- `app/routers/login.py` serves the Japanese HTML login flow (`/login`,
  `/logout`, `/`) with Jinja2 templates. A successful login stores `user_id` in
  the Starlette session. `app/security.py` implements the `login_required`
  dependency for these session-protected pages.
- `app/routers/timetable.py` is the JSON/API boundary for the companion
  `time-table-to-line` app. It issues the handoff token, refreshes tokens,
  serves group/event APIs, and owns milestone CRUD and state transitions.
- `app/tokens.py` implements HS256 JWTs and hybrid transport. A Bearer token in
  `Authorization` is preferred; httpOnly `access_token` and `refresh_token`
  cookies are the fallback. `require_token` also checks that the `StaffLogin`
  referenced by the JWT still exists.
- `app/database_base.py` provides the SQLAlchemy engine, `SessionLocal`, `Base`,
  and request-scoped `get_db` dependency. `app/config.py` builds the PostgreSQL
  URL from environment variables or `DATABASE_URL` and owns token, session, and
  scheduler settings.
- `app/models.py` maps the legacy tables (`M_STAFFINFO`, `M_TEAM`,
  `M_LOGININFO`, `T_TIMELINE_EVENT`) plus `M_MILESTONE`; `app/schemas.py`
  contains Pydantic request models. The event serializer is the API compatibility
  boundary consumed by the frontend.
- `app/jobs/close_milestones.py` contains the pure milestone close operation and
  the scheduler entry point. It is intentionally called outside a request, so
  the background job opens its own SQLAlchemy session.
- Tests use `TestClient` and override `get_db` with an in-memory SQLite engine
  using `StaticPool` and `check_same_thread=False`. They seed user, login, team,
  and event rows in `tests/conftest.py`; no real PostgreSQL database is needed
  for the test suite.

## Key conventions

- Read `AGENTS.md` and `requirement-02.md` before changing authentication or
  database behavior. For milestone changes, read both `requirement-03.md` and
  `.hermes/rules/milestones.md`; the latter is the frequently updated source of
  milestone rules. For behavior changes, also inspect the newest dated file in
  `specs/` and `docs/architecture/`.
- Application request handlers and dependencies must receive
  `db: Session = Depends(get_db)`; do not create `SessionLocal()` in routers or
  request dependencies. The standalone scheduler job is the exception because
  it runs without a request dependency.
- Preserve legacy table names and uppercase model attributes. Do not rename or
  reshape `EventORM.to_dict()`: its keys are `id`, `staff_id`, `group`, `start`,
  `end`, `title`, `summary`, `progress`, `milestone_id`, and `completed`, with
  timestamps formatted as `%Y-%m-%dT%H:%M:%S.000Z`.
- Preserve the `time-table-to-line` token contract. `/timetable/auth` returns a
  303 redirect to `{APP_URL}/auth?token=<access-token>` and sets both auth
  cookies. `/refresh` accepts the existing client contract (access or refresh
  JWT) and returns JSON containing a new `access_token` while refreshing the
  access cookie.
- Access JWT claims are `user_id`, `group_id`, `admin`, `type`, and `exp`.
  Timetable and milestone APIs use `Depends(require_token)`; HTML pages use
  `Depends(login_required)`. Keep Werkzeug
  `generate_password_hash`/`check_password_hash` for existing password hashes.
- Keep session cookies httpOnly and set `https_only=True` when `ENV=production`.
  Never read, print, expose, or commit `.env` contents or credentials.
- Use Pydantic models with `Annotated[..., Form()]` for HTML form bodies.
  Templates use request-first `TemplateResponse(request, ...)`. Ordinary
  redirects use `RedirectResponse(..., status_code=303)`; dependency-based
  redirects use an HTTP 303 with a `Location` header.
- Milestones are group-independent and use `open`, `waiting`, and `closed`.
  Admin claims are required for create/update/remove; `/milestone/remove` is a
  soft close. Setting `accomplished_date` moves a milestone to `waiting` and
  marks child events completed; explicitly sending `accomplished_date: null`
  reopens it and resets those child events to incomplete. Closed milestones
  cannot be updated.
- Milestone colors come from the fixed palette in
  `app/routers/timetable.py`; colors used by `open` or `waiting` milestones are
  avoided before cycling. The frontend relies on `#2196f3` for the default event
  color and `#ffc107` for the clicked color.
- The APScheduler job closes `waiting` milestones after
  `MILESTONE_CLOSE_GRACE_DAYS` (default 5), using the inclusive
  `accomplished_date + grace_days <= today` boundary. Its interval is controlled
  by `MILESTONE_CLOSE_INTERVAL_MINUTES`; set
  `ENABLE_MILESTONE_SCHEDULER=false` for development/tests when needed.
- Do not run Alembic migrations automatically. PostgreSQL migration execution is
  intentionally manual. Do not reintroduce the removed Flask modules
  (`routes.py`, `auth_middleware.py`) or Flask imports.
- UI copy is Japanese and templates are plain HTML/htmx-oriented, not
  Bootstrap-based.

## Repository guidance and review workflow

`AGENTS.md` and `GEMINI.md` provide the repository-wide context. The
`.github/agents/pr-review.md` agent requires checking the relevant issue,
newest dated spec, newest dated architecture document, PR/diff, and recording
Japanese review results under `.github/reports/` without modifying source code.
