# Copilot instructions for light-token-server

## Build, test, and lint commands

This repo targets Python 3.13 and uses `uv`.

```bash
source .venv/bin/activate
```

Run the full suite:

```bash
source .venv/bin/activate && uv run pytest
```

Run one test module or one specific test:

```bash
source .venv/bin/activate && uv run pytest tests/test_milestone.py
source .venv/bin/activate && uv run pytest tests/test_login.py::test_login_success_sets_session
```

Run the dev server:

```bash
source .venv/bin/activate && uvicorn app.main:app --reload
```

`pyproject.toml` configures pytest to use `tests/` and adds the repo root to `PYTHONPATH`. There is no project-level lint command configured in this repo.

## High-level architecture

- `app/main.py` builds the FastAPI app, installs `SessionMiddleware` and credentialed CORS, includes the login and timetable routers, exposes `/health`, and starts the optional milestone scheduler in the FastAPI lifespan.
- `app/config.py` centralizes environment-derived settings: DB URL, token/session secrets, app URL, milestone scheduler parameters, and expiry windows.
- `app/database_base.py` defines the SQLAlchemy engine, `SessionLocal`, `Base`, and the request-scoped `get_db` dependency.
- `app/models.py` maps the legacy tables and uppercase attribute conventions (`M_STAFFINFO`, `M_TEAM`, `M_LOGININFO`, `T_TIMELINE_EVENT`, `M_MILESTONE`) and is the compatibility layer for the frontend.
- `app/routers/login.py` handles the Japanese HTML login flow (`/login`, `/logout`, `/`) with Jinja2 templates; successful login stores `user_id` in the Starlette session.
- `app/routers/timetable.py` is the main JSON/API boundary for the companion `time-table-to-line` app. It issues handoff tokens, refreshes access tokens, serves group/event APIs, and owns milestone CRUD/state transitions.
- `app/tokens.py` implements the HS256 JWT + hybrid transport pattern: prefer `Authorization: Bearer ...`, with httpOnly cookies as the fallback. `require_token` also verifies the referenced `StaffLogin` still exists.
- `app/jobs/close_milestones.py` contains the milestone-closing business logic and is intentionally run outside a request context, so it opens its own SQLAlchemy session.
- Tests use FastAPI `TestClient` and override `get_db` with an in-memory SQLite engine (`StaticPool`). The fixtures in `tests/conftest.py` seed user/login/team/event rows, so no real PostgreSQL is required for the default test run.
- The repo includes an MCP configuration at `.mcp.json` with a `code-review-graph` server, and `.claude/settings.json` hooks it into editor commands.

## Key conventions

- Read `AGENTS.md` and `requirement-02.md` before changing authentication or database behavior. For milestone changes, read both `requirement-03.md` and `.hermes/rules/milestones.md`; if a behavior change touches a larger feature, also check the newest dated file in `specs/` and `docs/architecture/`.
- Request handlers and dependencies should receive `db: Session = Depends(get_db)`. Do not open `SessionLocal()` inside request handlers or request-scoped dependencies; the scheduler job is the exception because it runs without a request dependency.
- Keep the legacy schema conventions intact: preserve table names, uppercase model attributes, and the `EventORM.to_dict()` contract. Its keys are `id`, `staff_id`, `group`, `start`, `end`, `title`, `summary`, `progress`, `milestone_id`, and `completed`, with timestamps formatted as `%Y-%m-%dT%H:%M:%S.000Z`.
- Preserve the `time-table-to-line` token contract: `/timetable/auth` redirects to `{APP_URL}/auth?token=<access-token>` and sets both auth cookies, while `/refresh` accepts the existing client contract (access or refresh JWT) and returns a new `access_token` plus refreshed cookie state.
- Access JWT claims are `user_id`, `group_id`, `admin`, `type`, and `exp`. Timetable and milestone APIs use `Depends(require_token)`; HTML pages use `Depends(login_required)`.
- Keep session cookies `httpOnly`; set `https_only=True` when `ENV=production`. Do not expose, print, or commit `.env` content or secrets.
- Use Pydantic models with `Annotated[..., Form()]` for HTML form bodies, and use `TemplateResponse(request, ...)` for page responses. Redirects should follow the repo's normal patterns: 303 redirects for normal handoff flows and `HTTPException(303, headers={"Location": ...})` in dependencies.
- Keep milestone behavior aligned with `requirement-03.md` and `.hermes/rules/milestones.md`: statuses are `open`, `waiting`, and `closed`; milestone writes are admin-only; `/milestone/remove` is a soft close; setting `accomplished_date` moves a milestone to `waiting`, and clearing it explicitly reopens a waiting milestone. A `closed` milestone is terminal.
- Follow the configured milestone color palette and scheduler semantics in `app/routers/timetable.py` and `app/jobs/close_milestones.py` rather than inventing custom milestone rules.
- Milestones are shared across groups. `/milestone/all` returns open and waiting milestones; `/milestone/closed` is admin-only. Open/waiting `GET /milestone/{id}/events` is available to any authenticated user, while `GET /milestone/closed/{id}/events` is admin-only. Both event endpoints include events across groups and use the `EventORM.to_milestone_dict()` whitelist, which excludes `summary`; the regular event APIs retain their existing `to_dict()` response.
- `_get_milestone_events` fetches team names in one query rather than querying once per event. Preserve this batching when changing milestone event responses.
- For milestone event retrieval changes, use `specs/2026-10-13-milestone-event-retrieval-spec.md` as the API contract and consult the matching dated change record in `specs/` or `docs/architecture/`; dated architecture files are snapshots, not necessarily the current contract.
- Do not run Alembic migrations automatically; PostgreSQL migration execution is intentionally manual. Do not reintroduce the removed Flask modules (`routes.py`, `auth_middleware.py`) or Flask imports.
- UI copy is Japanese, and templates are plain HTML/htmx-oriented rather than Bootstrap-based.
