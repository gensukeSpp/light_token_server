# Issue-2 実装計画 — アクセストークン/CRUD を FastAPI で動かす

> **For Hermes:** 実装は subagent-driven-development を使用してタスク単位で進める。

**Goal:** GitHub Issue #2「[Refactor]Flask -> FastAPI 第2弾」のとおり、`app/auth_middleware.py` と `app/routes.py` の **Flask 依存 -> FastAPI** を完了させ、アクセストークン・リフレッシュトークンを **httpOnly Cookie** で管理し、JWT ペイロードに **`admin`** を追加して、フロントエンド(time-table-to-line)へ `admin: boolean` を届けられる状態にする。

**Architecture:** JWT の発行/検証を FastAPI 向けの独立モジュール(`app/tokens.py`)に抽出。Flask の `@token_required` デコレータは FastAPI の依存(`Depends(require_token)`)へ置換。CRUD ルート群を `app/routers/timetable.py`(FastAPI `APIRouter`)へ移植し、`main.py` に登録。DB アクセスはすべて `get_db` 依存経由に統一。移行・検証が終わった時点で旧 Flask の `routes.py` / `auth_middleware.py` を削除する。

**Tech Stack:** FastAPI, uvicorn, SQLAlchemy(2.x), PyJWT(HS256), Starlette `SessionMiddleware`(既存) + Response Cookie(httpOnly), pydantic, pytest + httpx(テスト用 SQLite)

---

## この段階で完成するもの(成果物)

- ログイン済み(`/timetable/auth`)で **アクセストークンとリフレッシュトークンを httpOnly Cookie** として発行し、フロントへ遷移する
- どちらのトークンも **長めの有効期限**(限定組織向け、env で調整可能)
- JWT ペイロードに **`admin: bool`**(`StaffLogin.ADMIN`)を追加。既存の `user_id` / `group_id` と併せて `{ user_id, group_id, admin, type, exp }`
- `/refresh` でリフレッシュトークンから新しいアクセストークンを再発行
- `/timetable/inquiry` 等の CRUD エンドポイントが **httpOnly Cookie のトークン**で認証され、FastAPI で応答する
- フロントエンドが `admin: boolean` を取得できる(下記「判断ポイント 1」を参照)
- `app/` 配下から Flask 依存が消え、`routes.py` / `auth_middleware.py` が削除される
- テスト(`tests/`)が SQLite で自動・再現可能に通る

## スコープ外(今回はやらない)

- PostgreSQL への **DB マイグレーション本体 — 利用者本人が実施**(ここでは接続設定・SQLite テストのみ)
- パスワードハッシュ方式の刷新(werkzeug 維持)
- リフレッシュトークンの **DB 側での失効管理・ローテーションの厳格化**(必要になったら別 issue)
- フロントエンド側の改修(利用者が両者を起動して確認する)

## 現在のコンテキスト / 前提

- 前段階(Issue #1 / Task-01)でログインは FastAPI 化済み: `main.py` + `routers/login.py` + `schemas.py` + `security.py`(`login_required`)+ `config.py` + `database_base.py`。`SessionMiddleware` でセッションに `user_id` を保持。
- `app/__init__.py` は**空**。`routes.py` / `auth_middleware.py` は現状 Flask(`from . import app, db` を参照)だが、`app/__init__.py` が空のため**現時点では壊れており、`main.py` はこれらを import していない**。
- `auth_middleware.py`: `token_required`(JWT を Authorization ヘッダから読むデコレータ)、`issue_token`(payload `{user_id, group_id}`、**exp なし**)、`get_user_group_id`。未使用の `get_user_group` も存在。
- `routes.py`: `/timetable/auth`(ログイン後アクセストークン発行→`?token=`でフロントへリダイレクト)、`/refresh`、`/timetable/inquiry`、`/group/all`、`/group/users`、`/event/all`、`/event/user`、`/group-names`、`/event/add`、`/event/update/<id>`、`/event/remove/<id>`。`convert_strToDate` ヘルパあり。
- `models.py`: `StaffLogin.ADMIN`(Boolean)は**既に存在**。`EventORM.to_dict()`、`User.STAFFID/TEAM_CODE`。
- テスト基盤: `tests/conftest.py` で SQLite + `get_db` 上書き + `User(1001)`/`StaffLogin(1001, "secret", True)` シード。
- 依存済み: `pyjwt`, `fastapi`, `sqlalchemy`, `httpx` ほか。**Flask 系(fastapi/flask, flask_login, flask_cors)は manifest に依存として存在しない**。

## 構成方針の要点

- **トークンロジックの分離**: `app/tokens.py`(新規)に JWT 発行/検証と Cookie ヘルパを集約。`security.py`(ログインセッション用)とは役割を分ける。
- **認可の置換**: Flask デコレータ `@token_required` → FastAPI 依存 `Depends(require_token)`。Cookie 内のアクセストークンを decode して claims(`user_id`,`group_id`,`admin`)を返す。
- **DB アクセス**: すべて `db: Session = Depends(get_db)`。Flask の `db.session` 参照を排除。`get_user_group_id` も `db` 引数へ。
- **Cookie**: 発行応答に `response.set_cookie(..., httponly=True, samesite=..., max_age=...)` でアクセス/リフレッシュを設定。フロントとのクロスオリジン授受は「判断ポイント 1」参照。
- **CORS**: `main.py` に `CORSMiddleware`(origins = `APP_URL` + `http://localhost:5173`, `allow_credentials=True`)を追加。
- **ペイロード**: `{ user_id, group_id, admin, type("access"|"refresh"), exp }`。`ADMIN` を既存 claims に合わせて追加。
- **削除**: 移行完了・検証後に `git rm app/routes.py app/auth_middleware.py`。

## 判断ポイント(実装前に利用者へ確認)

1. **フロントへの `admin` 授受方法 / Cookie のクロスオリジン** — ⭐最重要
   - 問題: フロント(localhost:5173)とバックエンド(localhost:8000)は**別オリジン**。バックエンドがセットした **httpOnly Cookie はフロントの JS から読めず、また別オリジンには自動送信されない**(SameSite 制約)。
   - オプション(A) **JSON エンドポイント経由**: `/timetable/inquiry`(または `GET /me` を新設)の応答に `admin: bool` を含め、フロントが `credentials: "include"` で取得。JWT ペイロードには backend 認可用に `admin` を入れておく。**推奨**。
   - オプション(B) **Same-Origin 化**: 本番は反応プロキシ/リバースプロキシで `/api` を同一オリジン化し、開発は Vite プロキシ + SameSite=None/`Secure` を組み合わせて httpOnly Cookie を直接共有。
   - オプション(C) **手渡し維持**: 従来どおり `?token=`(またはレスポンス本文)でフロントへ渡し、フロントが JWT を decode して `admin` を読む。httpOnly と両立しないため、issue の「httpOnly Cookie で管理」とトレードオフ。
   - → **既定は (A)** として tasks を書く。利用者判断を仰ぐ。
2. **有効期限の具体的値**: 限定組織向け「長め」。既定は アクセス **24h** / リフレッシュ **30日**(env で調整可)。これで良ければ確定、変えたいなら値だけ変更。
3. **`/group/all` の旧 filter の扱い**: 旧コードは `query(EventORM).filter(Team.CODE == ...)`(JOIN なしで Team.CODE を参照 = 実質不整合)。本移行では **`EventORM.group_id == claims["group_id"]` に直す**方針。挙動を完全互換にしたい場合は指示をもらう。

## ディレクトリ構成(実装後)

```
app/
  __init__.py
  main.py            # 編集: CORSMiddleware + timetable ルーター登録
  config.py          # 編集: トークン有効期限 env 追加
  database_base.py   # 不変
  models.py          # 不変(StaffLogin.ADMIN は既存)
  schemas.py         # 不変
  security.py        # 不変(ログインセッション用 login_required)
  tokens.py          # 新規: JWT 発行/検証 + httpOnly Cookie ヘルパ
  routers/
    __init__.py
    login.py         # 不変
    timetable.py     # 新規: 移植した CRUD + /timetable/auth + /refresh
  routes.py          # 削除(移行完了後)
  auth_middleware.py # 削除(移行完了後)
tests/
  conftest.py        # 編集: Team / EventORM シード追加
  test_tokens.py     # 新規: ペイロードに admin・期限
  test_timetable.py  # 新規: auth フロー・保護付きエンドポイント
```

## 着手順・依存

```
Task1(設計固め) → Task2(tokens.py) → Task3(ルーター/CRUD) → Task4(main 統合)
    → Task5(テスト整備) → Task6(検証・掃除) → Task7(Flask 削除)
```
- Task 2–4 が順依存。Task 5 は各タスクの実装を検証するため間に挟んでも良い(TDD 順を守る)。
- 各タスクは **TDD(失敗→実装→成功→Commit)** で 2–5 分規模。
