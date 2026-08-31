# Copilot instructions — light-token-server

## Build, test, and lint commands

The repository targets Python 3.13 and manages dependencies with `uv`. The virtual
environment is not automatically activated:

```bash
source .venv/bin/activate
```

Run the full test suite:

```bash
source .venv/bin/activate && uv run pytest
```

Run one test or one test module:

```bash
source .venv/bin/activate && uv run pytest tests/test_login.py::test_login_success_sets_session
source .venv/bin/activate && uv run pytest tests/test_milestone.py
```

Run the development server:

```bash
source .venv/bin/activate && uvicorn app.main:app --reload
```

`pyproject.toml` defines pytest's test path as `tests/` and adds the repository
root to `PYTHONPATH`. No project lint script or lint configuration is currently
defined.

## High-level architecture

- `app/main.py` creates the FastAPI application, installs session and CORS
  middleware, includes the login and timetable routers, and exposes `/health`.
- `app/routers/login.py` implements the Japanese HTML login flow (`/login`,
  `/logout`, `/`) with Jinja2 templates in `app/templates/`. Successful login
  stores `user_id` in the Starlette session.
- `app/routers/timetable.py` implements the token handoff to the companion
  `time-table-to-line` app, refresh, event/group APIs, and milestone APIs.
- `app/tokens.py` handles HS256 JWT creation/validation and the hybrid auth
  transport: `Authorization: Bearer ...` is preferred, with httpOnly
  `access_token`/`refresh_token` cookies as fallback. `require_token` also
  verifies that the referenced `StaffLogin` still exists.
- `app/security.py` provides the session-based `login_required` dependency;
  `app/database_base.py` owns the SQLAlchemy engine/session factory and the
  `get_db` dependency; `app/config.py` loads database, application URL, session
  secret, and token lifetime settings from the environment.
- `app/models.py` maps the legacy database schema (`M_STAFFINFO`, `M_TEAM`,
  `M_LOGININFO`, `T_TIMELINE_EVENT`) plus milestone tables. Pydantic request
  models live in `app/schemas.py`.
- Tests use FastAPI `TestClient` and override `get_db` with an in-memory SQLite
  database using `StaticPool`, so schema setup and dependency overrides are part
  of the test architecture rather than a real database requirement.

## Key conventions

- Read `AGENTS.md` and `requirement-02.md` before changing authentication or
  database behavior. For any milestone work, read
  `.hermes/rules/milestones.md` and `requirement-03.md`; the milestone rules are
  intentionally maintained separately because they change frequently.
- All application database access must use `db: Session = Depends(get_db)`.
  Do not instantiate `SessionLocal()` directly in routers, dependencies, or
  services; tests rely on overriding `get_db`.
- Preserve legacy table and column names, including uppercase model attributes.
  Preserve `EventORM.to_dict()` output keys and its timestamp format
  `%Y-%m-%dT%H:%M:%S.000Z`.
- Keep the token contract with `time-table-to-line`: `/timetable/auth` redirects
  with `?token=<access-token>` and sets auth cookies; `/refresh` accepts the
  existing client token contract and returns JSON containing the new
  `access_token` while refreshing the cookie.
- Access JWT claims are `user_id`, `group_id`, `admin`, `type`, and `exp`.
  Protected timetable and milestone endpoints use `Depends(require_token)`;
  session-protected HTML pages use `Depends(login_required)`.
- Keep password compatibility through Werkzeug's
  `generate_password_hash`/`check_password_hash`. Do not replace it with a new
  hashing scheme without an explicit migration plan.
- Keep `SessionMiddleware` httpOnly behavior and enable `https_only` when
  `ENV == "production"`. Do not expose, log, or commit `.env` contents or
  credentials.
- Use Pydantic models with `Annotated[..., Form()]` for form bodies. Templates
  use request-first `TemplateResponse(request, ...)`; redirects should use the
  repository's Starlette-compatible `RedirectResponse(..., status_code=303)`
  pattern.
- Milestones are shared across groups and use the `open`, `waiting`, and
  `closed` states. `/milestone/remove` is a soft close, and setting
  `accomplished_date` transitions to `waiting` and completes child events.
  Preserve the fixed color palette and the event default/clicked colors defined
  by the milestone rules.
- Do not run Alembic/database migrations automatically. The repository owner
  performs the PostgreSQL migration separately.
- Do not reintroduce removed Flask modules or imports (`routes.py`,
  `auth_middleware.py`). The active application is FastAPI-only.
- UI copy is Japanese, and the templates are plain HTML/htmx-oriented rather
  than Bootstrap-based.

## Related repository guidance

`AGENTS.md`, `GEMINI.md`, `requirement-02.md`, `requirement-03.md`, and
`.hermes/rules/milestones.md` are authoritative project guidance. The local
`.github/agents/pr-review.md` defines the expected workflow and Japanese output
format for PR reviews; follow it when using that review agent.
