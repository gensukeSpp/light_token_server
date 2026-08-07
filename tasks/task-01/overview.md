# Task-01 実装計画 — ログインを FastAPI で動かす

> **For Hermes:** 実装は subagent-driven-development を使用してタスク単位で進める。

**Goal:** 既存の Flask ログインを **FastAPI で「ログインできる」状態**に移行する — スタッフ ID・パスワードでサインイン → httpOnly セッションクッキー発行 → 仮のリンク(ログイン成功)ページへ遷移、まで動くようにする。

**Architecture:** `app/` 配下を FastAPI 構成に再編。`main.py`(FastAPI app + CORS + セッション + ルーター登録)、`routers/login.py`(ログイン/ログアウト/リンクページ)、`schemas.py`(Pydantic フォーム)、`security.py`(セッション依存・パスワード)、`database_base.py`(PostgreSQL 接続)。既存 `models.py` の旧スキーマ(タブル名・大文字カラム)は維持。

**Tech Stack:** FastAPI, uvicorn, SQLAlchemy, Jinja2, htmx(テンプレは Bootstrap 廃止), PyJWT, psycopg(binary), python-dotenv, python-multipart, itsdangerous(セッション), pytest + httpx(テスト用 SQLite)

---

## この段階で完成するもの(成果物)

- `uvicorn app.main:app` でサーバーが起動する
- `GET /login` → ログインフォームが表示される(Bootstrap 非依存・htmx)
- `POST /login` → 正しい資格情報で 302 遷移 + **httpOnly セッションクッキー**設定
- 未ログインで `/`(リンクページ)へアクセス → `/login` へリダイレクト
- ログイン成功後、仮のリンクページ(`/`)が表示され、time-table-to-line へのリンクとログアウトが置ける
- `POST /logout` → セッション破棄して `/login` へ
- テスト(`tests/`)が SQLite で自動・再現可能に通る

## スコープ外(今回はやらない)

- `routes.py`(CRUD・アクセストークン発行)の FastAPI 化 — **次段階**
- `auth_middleware.py` の JWT `token_required` / `issue_token` の移行 — **次段階**(ログインには不要)
- PostgreSQL への **DB マイグレーション本体 — 利用者本人が実施**(ここでは接続設定・テストを SQLite で用意するのみ)
- htmx による本格的な フロント刷新(仮リンクページの最小実装まで)
- パスワードハッシュ方式の本格刷新(後述の判断ポイント)

## 現在のコンテキスト / 前提

- 前段階でマニフェスト作成済み: `pyproject.toml` + `uv.lock`(FastAPI 依存のみ)。`uv run` で `.venv`(Python 3.13.11)が使える
- `app/` は現状 Flask: `login.py` / `form.py` / `routes.py` / `auth_middleware.py` / `database_base.py` / `models.py`。`app/__init__.py` は**存在しない**
- 未導入ライブラリ(調査済み): `itsdangerous`(セッション署名)、`werkzeug`(パスワード、**未導入**)、`passlib`、`bcrypt`
- `models.py` は SQLAlchemy `Base` を `from .database_base import Base` で参照
- テンプレは現在 Bootstrap 依存(`base.html` が `bootstrap/base.html` を extends、`login.html` が `bootstrap/wtf.html` を使用)→ **書き換えが必要**
- `.env` に DB 接続(`DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME`)あり。`SECRET_KEY` は未定義

## 構成方針の要点

- **モジュール分割**: `main.py` をエントリポイントとして円環 import を避ける(`uvicorn app.main:app`)。旧 `login.py` の Flask `app` オブジェクトは廃止
- **DB**: 接続設定は PostgreSQL(`postgresql+psycopg://`)に切替。ただし自動テストは SQLite インメモリ + `get_db` 依存を上書きして実行 → **実 DB が無くてもログインロジックを検証可能**
- **セッション**: Starlette `SessionMiddleware`(itsdangerous 署名クッキー、既定 httpOnly)。`SECRET_KEY` は env から(無ければ開発用フォールバック)
- **フォーム**: `form.py`(Flask-WTF)を廃止し `schemas.py`(Pydantic)へ
- **パスワード**: 回答待ち判断ポイント(下記)。既定は **werkzeug を維持**(既存登録済みハッシュがそのまま検証できるため)

## 判断ポイント(実装前に利用者へ確認)

1. **パスワードハッシュ方式**
   - 既定推奨: **`werkzeug.security` を維持**(`werkzeug` を manifest に追加)。理由: 既存 `M_LOGGININFO.PASSWORD_HASH` は werkzeug 形式(pbkdf2)であり、そのままログイン検証できる。`werkzeug` は Flask 本体でなく単体の WSGI ユーティリティライブラリなので FastAPI と並存できる。
   - 代替: **`passlib[bcrypt]` へ切替**(FastAPI 純正に寄せる)が、既存の werkzeug ハッシュは bcrypt で検証不能 → 既存ユーザーの再ハッシュ/パスワードリセットが必要になり「ログインできる」の即時達成を阻む。→ **後段リファクタ**として扱う。
2. **実 DB での手動ログイン確認**
   - 自動テストは SQLite で完結。実 DB(PostgreSQL)でのログインは利用者の DB マイグレーション後に対象。この段階の完了条件は「テストが通る + `uvicorn` 起動 + フォーム描画」とする。

## ディレクトリ構成(実装後)

```
app/
  __init__.py        # 空 or バージョン管理用(新規)
  main.py            # FastAPI app + CORS + SessionMiddleware + ルーター登録 + Jinja2(新規)
  config.py          # env 読み込み: DB_URL, SECRET_KEY, ENV(新規)
  database_base.py   # 編集: URL を postgresql+psycopg に、get_db 依存を追加(models からの import は不変)
  models.py          # ほぼ不変(旧スキーマ維持)。check_password は werkzeug のまま
  schemas.py         # Pydantic フォーム(新規。form.py の置換)
  security.py        # login_required 依存 + セッション読み書き(新規)
  routers/
    __init__.py      # (新規)
    login.py         # GET/POST /login, /logout, GET /(新規)
  templates/
    base.html        # 書き換え: Bootstrap 廃止・htmx 化
    login.html       # 書き換え: htmx フォーム
    index.html       # (新規)仮リンク(ログイン成功)ページ
  form.py            # 削除(Flask-WTF)
  login.py           # 削除(旧 Flask ログイン。routers/login.py に置換)
  routes.py          # 変更しない(次段階)
  auth_middleware.py # 変更しない(次段階)
tests/
  conftest.py        # SQLite engine + App/TestClient + StaffLogin シード + get_db 上書き
  test_login.py      # ログインフロー・セッション・失敗系
```