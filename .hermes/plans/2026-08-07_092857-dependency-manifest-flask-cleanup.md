# 依存マニフェスト作成 + Flask 依存の整理 — 実装プラン (第 1 段階: マニフェストのみ)

> **For Hermes:** 実装は subagent-driven-development を使用してタスク単位で進める。

**Goal:** `uv` による依存マニフェスト (`pyproject.toml` + `uv.lock`) を作成し、FastAPI ターゲットスタックの依存だけを宣言する最小構成に整える。**コードの Flask→FastAPI 移行は今回は行わない**(別スコープ)。

**Architecture:** 既存 `app/` は現状維持。ルートに `uv init` で最小の `pyproject.toml` を作り、`uv add` で FastAPI 系依存のみ宣言して `uv.lock` を生成・解決可能にする。現行 Flask コードはこの環境では実行できない状態のまま(今日時点で元々実行不可: マニフェスト・`__init__.py` なし)。

**Tech Stack:** uv (0.9.18), Python 3.13, FastAPI / uvicorn / SQLAlchemy / Alembic / Jinja2 / httpx / Pydantic / pytest / PyJWT / psycopg(binary) / python-dotenv / python-multipart

---

## Goal(この段階で完成するもの)

- `pyproject.toml` が存在し、FastAPI ターゲット依存のみを正しく宣言している
- `uv.lock` が生成され、`uv sync` で解決・インストールできる
- `uv run pytest` が「テストが無い」以外は起動できる(現状 `tests/` 空なので `no tests ran` で正常終了)

## Current context / assumptions

- リポジトリ: `light_token_server`(branch `refactor/de-flask-dependency`)
- `app/` は全ファイル Flask のまま(`login.py` / `routes.py` / `auth_middleware.py` / `form.py` / `database_base.py` / `models.py`)
- マニフェストなし・`app/__init__.py` なし・`tests/` 空 = **現状実行不可**(これは既知の前提)
- `uv` 0.9.18 インストール済み / ローカル `python3` は 3.12 だが `uv` が 3.13 を取得する
- `.gitignore` は `.venv/` と `.env` を除外済み(追跡外のまま。触らない)
- **DB マイグレーションは実施しない**(利用者本人が行う)。ここでは Alembic の依存宣言のみ
- 対象スタックは requirement-02 準拠: FastAPI, uvicorn, sqlalchemy, alembic, jinja2, httpx, Pydantic, pytest「ほか」

## Proposed approach

1. `uv init` で最小の `pyproject.toml` をルートに生成(Python 3.13 ピン)
2. ランタイム依存を `uv add` で宣言(FastAPI 系のみ)
3. 開発依存を `uv add --dev pytest` で宣言
4. `uv.lock` 生成 → `uv sync` で解決確認
5. 変更コミット

## Step-by-step plan

### Task 1: `uv init` でプロジェクトを初期化

**Objective:** ルートに最小の `pyproject.toml` を生成する。

**Files:**
- Create: `pyproject.toml`(生成)
- Create: `.python-version`(生成)

**Step 1:** プロジェクトルートで初期化。
```bash
cd /home/nabu_dvl/workspace/the-calendar-to-timeline/light_token_server
uv init --bare --python 3.13
```
- `--bare`: パッケージ構造(src レイアウト等)を作らない最小構成
- `--python 3.13`: requirement の Python 3.13.x にピン(`.python-version` が `3.13` になる)

**Step 2:** 生成確認。
```bash
cat pyproject.toml && cat .python-version
```
Expected: `name = "light-token-server"`, `requires-python = ">=3.13"`, `[dependency-groups]` が存在。

**Step 3:** Commit
```bash
git add pyproject.toml .python-version
git commit -m "chore: uv init でプロジェクト初期化 (Python 3.13)"
```

---

### Task 2: FastAPI ランタイム依存を宣言

**Objective:** ターゲットスタックのランタイム依存のみを `uv add` で追加する。

**Files:**
- Modify: `pyproject.toml`(dependencies 追加)
- Create: `uv.lock`(生成)

**Step 1:** 依存を追加。
```bash
uv add fastapi 'uvicorn[standard]' sqlalchemy alembic jinja2 httpx PyJWT \
  'psycopg[binary]' python-dotenv python-multipart
```
内訳(requirement-02 準拠 + アプリが実際に使うもの):
- `fastapi`, `uvicorn[standard]` — FastAPI サーバー
- `sqlalchemy`, `alembic` — ORM + マイグレーション(マイグレーション実行は利用者)
- `jinja2` — テンプレート(htmx 化は別段階だがライブラリは必要)
- `httpx` — (a) テスト用 TestClient、(b) time-table-to-line 連携
- `PyJWT` — 既存 `auth_middleware.py` の HS256 JWT と同ライブラリ
- `psycopg[binary]` — PostgreSQL ドライバ(DB 移行後のターゲット)
- `python-dotenv` — 既存 `database_base.py` が `.env` 読み込みに使用
- `python-multipart` — FastAPI のフォームログイン(form 解析)に必須

**Step 2:** 解決確認。
```bash
uv lock && uv sync
```
Expected: `uv.lock` が生成され、`uv sync` がエラーなく完了(`.venv/` にインストール)。依存グラフ競合が起きれば printout で解消。

**Step 3:** 依存一覧を確認。
```bash
uv pip list | head -40
```
Expected: fastapi, uvicorn, sqlalchemy, alembic, jinja2, httpx, PyJWT, psycopg 等が存在。

**Step 4:** Commit
```bash
git add pyproject.toml uv.lock
git commit -m "chore: FastAPI ランタイム依存を宣言 (uv add)"
```

---

### Task 3: 開発依存(pytest)を宣言

**Objective:** テスト用の dev 依存を追加する。

**Files:**
- Modify: `pyproject.toml`(`[dependency-groups] dev`)

**Step 1:**
```bash
uv add --dev pytest
```

**Step 2:** テスト実行が起動できることを確認(テストがないので no tests ran で正常終了)。
```bash
uv run pytest
```
Expected: exit 0、`no tests ran`(現状 `tests/` が空なのは既知)。

**Step 3:** Commit
```bash
git add pyproject.toml uv.lock
git commit -m "chore: 開発依存に pytest を追加"
```

---

### Task 4: 検証(マニフェストのみのスコープ確認)

**Objective:** マニフェストが壊れていないこと、今回のスコープが守られていることを確認する。

**Step 1:**
```bash
uv lock --check
uv sync --frozen
uv run python -c "import fastapi, sqlalchemy, jwt, jinja2, httpx; print('deps ok')"
```
Expected: すべて正常終了。

**Step 2:** Flask 依存が**宣言されていない**ことを確認(=スコープ: FastAPI のみ)。
```bash
uv pip list | grep -iE 'flask|flask-login|flask-cors|flask-sqlalchemy|flask-wtf|wtforms|werkzeug|pymysql' || echo "Flask 系依存は宣言されていない(想定どおり)"
```
Expected: 何も一致しない。

> 注: 現行 `app/*.py` は Flask / werkzeug / pymysql / wtforms を import しているため、**このマニフェストの環境では実行不可**。これは意図どおり(移行は次段階)。逆に言うと、次段階の Flask→FastAPI 移行が終わるまで `app/` のコードはこの環境では動かない。

**Step 3:** `git status` で汚れがないことを確認(コミット後のクリーン状態)。

---

## Files likely to change(この段階)

- Create: `pyproject.toml`
- Create: `uv.lock`
- Create: `.python-version`
- (既存 `app/` 配下は変更しない)

## Tests / validation

- `uv run pytest` → `no tests ran` で exit 0
- `uv lock --check` / `uv sync --frozen` が成功
- Flask 系依存が宣言されていないことを grep で確認

## Risks, tradeoffs, and open questions

- **現行 Flask コードはこの環境で一時的に実行不可になる。** これは既に今日実行不可(マニフェスト・`__init__.py` なし)なため実害なし。ただし「マニフェストは完成、アプリはまだ動かない」状態が続く点は明示しておく。
- **ドライバ選択:** `psycopg[binary]` を採用(DB は利用者が PostgreSQL に移行予定のため)。移行が完了する前に一時的に MySQL で動かす必要が出た場合は `pymysql` を追加する判断が要る(この段階では不要)。
- **`pydantic-settings` は今回見送り**(最小構成のため)。`python-dotenv` で `.env` を読む現状に合わせる。設定管理を本格化する段階で検討。
- **パスワードハッシュ:** 現行 `models.py` は `werkzeug.security` を使用。これは Flask 系ライブラリなので**このマニフェストには含めない**。ログイン移行段階で `passlib[bcrypt]` 等へ差し替えを検討する(ここが移行スコープの論点)。
- **`uv init --bare` の妥当性:** src レイアウトは作らない方針。将来 `app/` をパッケージ化する際に `[tool.uv] package` や `packages` 設定を追加する。
- **次の段階の論点(今回は実施しない):** Flask→FastAPI を「ログインが動くところまで」にするか「Flask 依存 4 ファイル(`login.py`/`form.py`/`routes.py`/`auth_middleware.py`)全部」にするか。このマニフェストが次段階の土台になる。

## Execution handoff

プランは `.hermes/plans/2026-08-07_092857-dependency-manifest-flask-cleanup.md` に保存済み。

次段階(Flask→FastAPI 移行)のスコープは「ログインが動くところまで」か「Flask 依存 4 ファイル全て」かで分かれるため、このマニフェスト段階の実装完了後に利用者へ確認する。
