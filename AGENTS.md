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

## Milestones (requirement-03.md)

マイルストーン機能の要件(テーブル定義・状態遷移・権限・色・API・UI 規約)は、
更新が頻繁なため **`.hermes/rules/milestones.md`** に分割してあります。

→ **必須ルール: マイルストーン関連の変更・実装を行う前は必ず
`[.hermes/rules/milestones.md](.hermes/rules/milestones.md)` を読み、従うこと。**

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

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**This project has a knowledge graph. Start with the code-review-graph
MCP tools to narrow scope, then read the source.** The graph is cheaper than scanning files and
gives you structural context (callers, dependents, test coverage) that file search cannot.

> 注: このリポジトリでは `.code-review-graph/graph.db` が未構築です。
> 初回はプロジェクトルートで `code-review-graph build` (必要なら `graph embed`) を
> 実行してから使ってください (SQLite グラフはリポジトリごとに作られます)。

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes_tool` or `query_graph_tool` instead of Grep
- **Understanding impact**: `get_impact_radius_tool` instead of manually tracing imports
- **Code review**: `detect_changes_tool` + `get_review_context_tool` instead of reading entire files
- **Finding relationships**: `query_graph_tool` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview_tool` + `list_communities_tool`

### Verify in the source

- Narrow scope with the graph, then read the source. Do not change code from graph output alone.
- For any non-trivial change, read the implementation and the relevant tests before concluding.
- Verify the exact source when touching behavior, database logic, migrations, retries, fallbacks,
  recovery, or compatibility code.
- When the graph and the source disagree, the source wins. The graph may be stale or may not
  model that relationship.
- An empty graph result can mean "not indexed" or "not statically visible", not "does not exist".

### Key Tools

| Tool | Use when |
| ------ | ---------- |
| `detect_changes_tool` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context_tool` | Need source snippets for review — token-efficient |
| `get_impact_radius_tool` | Understanding blast radius of a change |
| `get_affected_flows_tool` | Finding which execution paths are impacted |
| `query_graph_tool` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes_tool` | Finding functions/classes by name or keyword |
| `get_architecture_overview_tool` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes_tool` for code review.
3. Use `get_affected_flows_tool` to understand impact.
4. Use `query_graph_tool` pattern=\"tests_for\" to check coverage.
<!-- /code-review-graph MCP tools -->

<!-- better-code-review-graph MCP tools -->
## MCP Tools: better-code-review-graph

**This is the successor MCP server for the same knowledge graph.** The graph DB
(`.code-review-graph/graph.db`) is shared by both servers, but the recent,
集約 API (`config` / `graph` / `query` / `review` / `security`) を後継とする。
新規の操作では **better 版を優先**し、旧 `*_tool` 名はレガシーとして扱う。
※ セキュリティスキャンは `security` ツールで実施可能 (OWASP 系 sink 検出。
  現時点では未実施、作業候補として扱う)。

### When to use better-code-review-graph FIRST

- **Code review**: `review(action=\"context\")` で変更 diff の影響範囲・ソース断片・
  レビュー指針を一度に生成 (旧 `detect_changes_tool` + `get_review_context_tool` に相当)
- **Refactor audit**: `review(action=\"delta\", show_line_shifts=true)` で関数の行移動を
  検出し、純粋リファクタコミットの呼び出し箇所を洗い出す
- **Code relationship**: `query(pattern=callers_of / callees_of / imports_of / tests_for)`
- **Semantic / keyword search**: `query(action=\"search\")` (embedding はローカル Qwen3 運用)
- **Blast radius**: `query(action=\"impact\")` で変更ファイルの依存 BFS を実行
- **Decomposition audit**: `query(action=\"large_functions\")` で長大関数・ファイルを検出
- **Security scanning** (作業候補): `security(action=\"scan\")` で SQL 注入 / シェル注入 /
  パストラバーサル / eval 注入 / ハードコードシークレットを検出。結果は
  `nodes.security_tags` に永続化され、`report(format=\"sarif\")` で GitHub 連携も可

### Key Tools

| Tool | Action | Use when |
| ------ | ---------- | ------ |
| `review` | `context` | 変更の影響範囲 + ソース断片 + レビュー指針を一度に得る |
| `review` | `delta` | 2 コミット間の add/remove/modify と関数行移動 (`show_line_shifts=true`) を監査 |
| `query` | `query` | callers_of / callees_of / imports_of / tests_for 等で関係を追跡 |
| `query` | `search` | 名前・キーワード・セマンティック検索 |
| `query` | `impact` | 変更ファイルの blast radius 分析 |
| `graph` | `build` / `update` / `embed` / `stats` | グラフ構築・更新・embedding・状態確認 |
| `security` | `scan` / `report` | セキュリティスキャン (現時点は未実施・作業候補) |

### Workflow

1. Code review は `review(action=\"context\", base=\"origin/main\")` でスコープを絞る
   (include_source=false でトークン節約可)。
2. 影響範囲を `query(action=\"impact\")` で確認する。
3. テスト網羅は `query(pattern=\"tests_for\", target=<func>)` で確認する。
4. 純粋リファクタ (ロジック不変) の監査は `review(action=\"delta\", show_line_shifts=true)`
   を利用する。
<!-- /better-code-review-graph MCP tools -->
