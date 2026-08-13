# Project: light-token-server

## Overview
Backend for login and access-token handling for the `time-table-to-line` application. 
Successfully migrated from legacy Flask/MySQL codebase to **FastAPI / PostgreSQL / Pydantic / htmx / uv / pytest**.

## Development Setup
- **Language:** Python 3.13 (pinned in `.python-version`)
- **Dependency Management:** `uv`
- **Virtual Environment:** Ensure `.venv` is activated:
  ```bash
  source .venv/bin/activate
  ```

## Development Commands
- **Run Tests:**
  ```bash
  uv run pytest
  ```
- **Run Server:**
  ```bash
  uvicorn app.main:app --reload
  ```

## Project Architecture & Conventions
- **Framework:** FastAPI
- **Database:** SQLAlchemy (migrating from MySQL to PostgreSQL). 
  - DB access must use `get_db` dependency.
  - Do NOT run database migrations; Alembic configuration is present, but execution is manually managed by the user.
- **Templates:** Jinja2 (no Bootstrap, using htmx).
- **Authentication:** JWT-based hybrid approach supporting both `httpOnly` session cookies and `Authorization: Bearer` headers for compatibility with existing clients.
- **Starlette 1.4.1:** Use `raise HTTPException(303, headers={"Location": ...})` for redirects instead of `RedirectResponse`.
- **Models:** Legacy schema (UPPERCASE columns).

## Security
- **NEVER** expose, log, or commit `.env` files (contains database credentials and application secrets).
- Ensure `https_only` is enabled in `SessionMiddleware` in production (`ENV == "production"`).

## Testing
- Tests use an in-memory SQLite database configured in `tests/conftest.py`.
- pytest configuration is located in `pyproject.toml`.

For detailed specifications and migration progress, refer to `requirement-02.md`, `AGENTS.md` and `docs/architecture/README.md` in the project root.
