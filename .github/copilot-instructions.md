# GitHub Copilot instructions — light-token-server

Short, repo-specific guidance for Copilot sessions working on this repository.

## Build, test, and lint commands
- Activate venv first (required):
  source .venv/bin/activate

- Run all tests (project uses uv as package runner):
  uv run pytest

- Run a single test (example):
  uv run pytest tests/test_login.py::test_login_success_sets_session

- Run server locally:
  source .venv/bin/activate && uvicorn app.main:app --reload

- Linting: no project lint tool/config detected. Apply repo-preferred linters (black/ruff/mypy) manually.

## High-level architecture (big picture)
- FastAPI backend located under `app/`.
  - app/main.py: FastAPI app, SessionMiddleware, router inclusion and `/health`.
  - app/routers/login.py: login/logout/index endpoints, Jinja2 templates under `app/templates`.
  - app/config.py: environment-driven config (DB URL, SECRET_KEY, ENV, APP_URL).
  - app/database_base.py: SQLAlchemy engine, SessionLocal, Base, and get_db dependency.
  - app/models.py: legacy schema (UPPERCASE column names and table names) used by ORM.
  - app/security.py: login_required dependency that reads session cookie and loads StaffLogin.
  - app/schemas.py: Pydantic schemas (forms).

- Tests: `tests/` use an in-memory SQLite engine and override `get_db` via TestClient (see tests/conftest.py). This is the canonical pattern for unit-tests here.

- Migrations: Alembic config is present (alembic.ini / migrations/) but running DB migrations is explicitly left to the repository owner; do not run them automatically in Copilot tasks.

## Key conventions (repo-specific)
- Always activate the provided virtualenv (.venv) before running `uv`, `pytest`, or `uvicorn`.

- DB access must use the FastAPI dependency `get_db` (db: Session = Depends(get_db)). Do NOT instantiate SessionLocal() directly in app code — tests override get_db.

- Legacy DB shape: models keep old table/column names (e.g. M_STAFFINFO, M_TEAM). Preserve column names and EventORM.to_dict() ISO timestamp format "%Y-%m-%dT%H:%M:%S.000Z" when working with serialization.

- Authentication: session-based httpOnly cookie implemented with Starlette SessionMiddleware (secret_key from env). In production ensure https_only when ENV=="production".

- Passwords: keep using werkzeug.generate_password_hash / check_password_hash so existing hashes remain valid.

- Templates: Jinja2 templates expect request-first TemplateResponse(request, "name.html", ctx). Redirects use HTTPException(303, headers={"Location": ...}) (Starlette 1.4.1 compatibility) rather than raising RedirectResponse.

- Forms: endpoint form bodies use Pydantic models + Annotated[Model, Form()] (requires python-multipart).

- Tests: When adding or modifying tests, follow tests/conftest.py pattern (StaticPool + sqlite:// memory) so TestClient thread worker retains tables.

- Environment: primary env variables used are DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME (or DATABASE_URL), SECRET_KEY, ENV, CLOUD_TIMETABLE4 (APP_URL). `.env` is gitignored — do not commit secrets.

## Existing AI-agent / assistant configs to incorporate
- AGENTS.md and GEMINI.md contain the repository migration plan and key constraints (activate venv, don't run migrations, keep legacy models). Use them as authoritative context.
- .github/agents/pr-review.md defines a local PR-review agent; Copilot sessions may invoke it for PR reviews.

## Quick checklist for Copilot sessions
- Read requirement-02.md and AGENTS.md before implementing auth/DB changes.
- Do not import or modify Flask-era modules `app/routes.py` or `app/auth_middleware.py` until they've been migrated to FastAPI.
- Preserve legacy model names/column case when touching models or serializations.
- Use dependency override pattern in tests when creating DB fixtures.


---

If helpful, configure an MCP server for end-to-end/browser testing (e.g., Playwright). Would you like an MCP server configured for Playwright or similar? (yes/no)
