# 2026-08-07 Architecture Snapshot: Flask to FastAPI Login Migration

## Purpose
Migrate the legacy Flask-based login authentication flow to FastAPI to modernize the backend infrastructure and align with the project's long-term technical roadmap.

## Overview
Replaced Flask with FastAPI for authentication routing, implementing `SessionMiddleware` for secure session handling and `get_db` dependency injection for PostgreSQL database interactions.

## Key Design Decisions
- **Framework Transition:** Adopted FastAPI for asynchronous support and type-safe schema validation (Pydantic).
- **Authentication:** Migrated to `SessionMiddleware` with `httpOnly` and `SameSite` flags to enhance security.
- **Data Layer:** Implemented `get_db` dependency to decouple database sessions, supporting migration from MySQL to PostgreSQL.
- **Frontend:** Removed Bootstrap and adopted htmx-compatible, lightweight templates.

## Next Steps
- Cleanup of deprecated assets (e.g., `app/templates/logout_msg.html`).
- Continue migration of remaining business logic (CRUD/access-token issuance) from Flask (`app/routes.py`, `app/auth_middleware.py`) to FastAPI.
- Complete database migration to PostgreSQL.

## Commits
- `Refactor/de flask dependency` (PR #1)

## Changed Files
- `app/main.py`
- `app/routers/login.py`
- `app/schemas.py`
- `app/security.py`
- `app/config.py`
- `app/database_base.py`
- `app/templates/` (base.html, login.html, index.html)
