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
- **Access tokens:** JWT HS256 (`PyJWT`) in `app/tokens.py`. Issued as **httpOnly cookies**
  (`access_token` + `refresh_token`) AND via `Authorization: Bearer <token>` header. Payload =
  `{user_id, group_id, admin, type, exp}`, where `admin` comes from `StaffLogin.ADMIN`. Long
  expiry for a limited org (defaults access 24h / refresh 30 days, env-tunable via
  `ACCESS_TOKEN_EXPIRE_HOURS` / `REFRESH_TOKEN_EXPIRE_DAYS`). Protected endpoints use
  `Depends(require_token)`.
- `app/models.py` keeps the legacy schema shape (UPPERCASE columns, tables `M_STAFFINFO`
  `M_TEAM` `M_LOGININFO` `T_TIMELINE_EVENT`) plus `M_MILESTONE` and `M_MILESTONE_EVENT`
  for milestone/task management (see Milestones section below).
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
- Auth (access token): JWT HS256 (`PyJWT`) lives in `app/tokens.py`. `get_token_claims`
  reads the token from the **`Authorization: Bearer <token>` header first, then the
  httpOnly cookie** (`access_token`/`refresh_token`) as fallback (the consuming
  `time-table-to-line` app sends Bearer headers; cookie keeps backward compat). Protected
  endpoints use `Depends(require_token)`; `/refresh` re-issues via
  `get_token_claims(request, {"access", "refresh"})` — accepts both token types so the
  old consuming app (which sends its **access** token to `/refresh`) keeps working.
  Payload keys: `user_id`, `group_id`, `admin`, `type`, `exp`.
- **Token/link contract with the consuming app (`time-table-to-line`):** `/timetable/auth`
  redirects to `{APP_URL}/auth?token=<access>` (303) with cookies also set; `/refresh`
  returns the new access-token **string in the body** (JSONResponse) with the cookie re-set.
  Keep these shapes — the frontend reads `?token=` from the URL and sends `Authorization:
  Bearer` on every request.
- DB access in FastAPI code **must** go through the `get_db` dependency
  (`db: Session = Depends(get_db)`), never a bare `SessionLocal()` — that's what lets tests
  override with SQLite.
- Forms: Pydantic schema + `Annotated[LoginForm, Form()]` (needs `python-multipart`).
- CORS: `allow_credentials=True` (httpOnly Cookie 認証に必須) で `allow_origins` は
  `os.getenv("CLOUD_TIMETABLE4")` + `http://localhost:5173`。
- DB URL built from env `DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME` (or `DATABASE_URL`).
- UI copy is Japanese; templates in `app/templates/`.
- Starlette 1.4.1: `TemplateResponse(request, name, {…})` is request-first, and you must
  `raise HTTPException(303, headers={"Location": …})` rather than `raise RedirectResponse`.
  See the `flask-to-fastapi-migration` skill for details.

## Milestones (`requirement-03.md`)

### Table schema
- `M_MILESTONE` — テーブル名は既存規則 (`M_STAFFINFO`) に合わせる
  - `id: Integer, primary_key`
  - `staff_id: Integer, ForeignKey("M_LOGININFO.STAFFID")` — 作成者ID
  - `title: String(100)`
  - `description: String(256), nullable`
  - `color: String(10)` — カラーコード
  - `status: String(10), default="open"` — `open` / `waiting` / `closed`
    (`waiting` は再 open の猶予期間 = waiting for close。定数 `MILESTONE_OPEN`/`MILESTONE_WAITING`/`MILESTONE_CLOSED` を models に定義)
  - `created_at: Date` — 作成日（時刻不要）
  - `guidline_end_date: Date, nullable` — 達成目安日
  - `accomplished_date: Date, nullable` — 達成日（入力=close）
- `T_TIMELINE_EVENT` に追加
  - `milestone_id: Integer, ForeignKey("M_MILESTONE.id"), nullable` — 所属マイルストーン
  - `completed: Boolean, default=False` — 完了フラグ

### Semantic rules
- `status="open"` → 作成直後。`status="closed"` → 達成済み。`status="waiting"` → 再 open の猶予期間（waiting for close）
- 一度 closed したら再 open 不可（API レイヤで拒否）
- マイルストーン close 時（`status`→`"closed"`）、属する全イベントの `completed` を `True` に自動更新
- `completed=True` または `milestone_id` が削除されたイベントはデフォルト色 (`#2196f3`) に変更
- マイルストーンはグループ横断共有。`group_id` カラムは不要

### Permission model
- `admin=True` のユーザー全員が作成/クローズ/削除可能
- 従来の「そのグループの管理者」→ 誤解を招く表現。実態は「全 admin ユーザー」
- 閲覧はグループ単位（既存のトークン `group_id` でフィルタ）

### Color rules
- 10 固定パターン: ` #9c27b0 #009688 #795548 #607d8b #e91e63 #3f51b5 #00bcd4 #ff5722 #8bc34a #ff9800`
- 作成時、open マイルストーンと被らない色を自動選択
- 10 件超えた場合は 1 番目の色から cyclic に戻す

### API endpoints
- `POST /milestone/add` — admin のみ、カラータブルから衝突回避
- `GET /milestone/all` — open マイルストーン一覧（`status="open"` のみ返す）
- `POST /milestone/update/{id}` — accomplished_date 設定で close
- `DELETE /milestone/remove/{id}` — admin のみ
- `POST /event/add` — `milestone_id` optional 追加
- `POST /event/update/{id}` — `completed` 対応

### UI conventions
- Japanese date format (UTC+9) for display only (stored as-is)
- Event default color: `#2196f3`
- Clicked color: `#ffc107`

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
