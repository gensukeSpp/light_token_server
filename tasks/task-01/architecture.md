# Task-01 アーキテクチャ詳細

## 1. モジュール構成と import の流れ

エントリポイントは `app/main.py`。`uvicorn app.main:app` で起動する。**円環 import を防ぐため `database_base.py` → `models.py` → `routers/*` → `main.py` の一方向に保つ。**

```
import 方向
app/database_base.py  (engine / Base / get_db)
   ^
app/models.py         (from .database_base import Base)  ← 不変
   ^
app/schemas.py        (Pydantic。独立)
app/security.py       (database_base + models を import)
   ^
app/routers/login.py  (schemas, security, database_base, models, templates)
   ^
app/main.py           (config, routers, templates)  ← 最上位。誰も import しない
```

- 旧 `app/login.py`(Flask `app` 生成)は削除。その Floyd `app` 参照に依存していた `routes.py` / `auth_middleware.py` は**次段階まで import しない**(main からは触らない)。→ この段階で破綻しない。

## 2. 設定: `app/config.py`(新規)

`python-dotenv` が `.env` を読み、ベタの `os.getenv` で組む(`pydantic-settings` は見送り。前段階のマニフェスト方針に合わせる)。

```python
import os
from dotenv import load_dotenv

load_dotenv()

def _db_url() -> str:
    return (
        "postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}".format(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            db_name=os.getenv("DB_NAME"),
        )
    )

DB_URL = os.getenv("DATABASE_URL", _db_url())
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-change-me")
ENV = os.getenv("ENV", "development")
```

- `DATABASE_URL` があれば最優先(Render/Neon 等の環境変数に対応)。
- `SECRET_KEY` は `ENV == "production"` で必須化する検証を hooks 等で。

## 3. データベース: `app/database_base.py`(編集)

変更点は 2 つ: (a) URL を psycopg 形式に、(b) FastAPI 依存 `get_db` を追加。`Base` / `session` の公開名は**維持**(`models.py` の `from .database_base import Base` を壊さない)。

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import DB_URL

engine = create_engine(DB_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- `create_engine` は遅延接続のため、テストで実 DB が無くても import は安全。
- 旧 `database_base.py` の `Session` / `session` 名称は使われている場所が `routes.py`(次段階)なので、`SessionLocal` を新設しつつ既存名も残すかは実装時に判断(最小 churn なら `Session` も alias で残す)。
- **注意:** DB マイグレーションは利用者本人。ここでは Alembic の `env.py` 設定は用意するが実行しない。

## 4. モデル: `app/models.py`(ほぼ不変)

- テーブル名(`M_STAFFINFO` / `M_TEAM` / `M_LOGGININFO` / `T_TIMELINE_EVENT`)、大文字カラム、`to_dict()` の ISO 形式は**そのまま**。
- `StaffLogin.check_password` / `__init__` の `generate_password_hash` は判断ポイント次第:
  - 既定: `werkzeug.security` を維持 → 変更なし
  - 切替時のみ: `passlib[bcrypt]` へ(この段階では選択しない)
- SQLAlchemy 2.0 の `Column` 記法はそのまま動作するため変更不要。
- ※ `relationship(backref=...)` の旧記法は 2.0 で warning が出ることがある。WARNING が気になる場合のみ `back_populates` へ(後段リファクタ枠)。

## 5. フォーム(Pydantic): `app/schemas.py`(新規)

`form.py`(Flask-WTF/WTForms)を置き換え。`python-multipart` でフォームボディをパース。

```python
from pydantic import BaseModel

class LoginForm(BaseModel):
    STAFFID: int
    PASSWORD: str
    remember_me: bool = False
```

- `STAFFID` は `M_STAFFINFO.STAFFID`(Integer)に合わせ `int`。`PASSWORD` は `str`。
- バリデーション失敗時は 422 が返るが、ページ表示(422 でもフォーム再描画)をどうするかはルーター側でハンドリング(下記)。

## 6. セキュリティ: `app/security.py`(新規)

- **セッション読み書き:** Starlette `SessionMiddleware` が設定する `request.session`(署名・httpOnly・SameSite cookie)を利用。`login_required` 依存でログイン中か判定。

```python
from fastapi import Request, HTTPException
from starlette.responses import RedirectResponse
from .database_base import SessionLocal
from .models import StaffLogin

def login_required(request: Request) -> StaffLogin:
    staff_id = request.session.get("user_id")
    if staff_id is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    db = SessionLocal()
    try:
        user = db.query(StaffLogin).filter(StaffLogin.STAFFID == staff_id).first()
        if user is None:
            raise HTTPException(status_code=303, headers={"Location": "/login"})
        return user
    finally:
        db.close()
```

- 未ログイン時は `/login` への 303 リダイレクト。※FastAPI では 303 用に小細工が要るので、実装時は `RedirectResponse` を `HTTPException` でなく直接 raise する方針に統一する(下記ルーター参照)。

## 7. ルーター: `app/routers/login.py`(新規)

`APIRouter` で以下を定義。`request` へのフォーム受け取りは `Form(...)` 互換の `LoginForm = Form` を使うか、`python-multipart` + Pydantic モデルで受ける。FastAPI でフォーム + 依存を同時に使うには `Annotated[LoginForm, Form()]` が最も素直。

```python
from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse
from .security import login_required
from .models import StaffLogin
from .database_base import SessionLocal

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@router.post("/login")
def do_login(request: Request, STAFFID: int = Form(...), PASSWORD: str = Form(...),
             remember_me: bool = Form(False)):
    db = SessionLocal()
    try:
        user = db.query(StaffLogin).filter(StaffLogin.STAFFID == STAFFID).first()
        if user is None or not user.check_password(PASSWORD):
            return templates.TemplateResponse(
                "login.html", {"request": request, "error": "ユーザ名かパスワードが違います"}, status_code=400)
        request.session["user_id"] = user.STAFFID
        # remember_me → クッキー有効期限の延長(実装時)
        return RedirectResponse("/", status_code=303)
    finally:
        db.close()

@router.post("/logout")
def do_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@router.get("/")
def index(request: Request, user: StaffLogin = Depends(login_required)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})
```

- **注意点:** `POST /login` のボディは `python-multipart` でパースされるため、マニフェストに `python-multipart` が入っている(前段階で追加済み)。
- `remember_me` の扱い: 未ログイン時の`SessionMiddleware` はサーバー側有効期限を持たない(単なる署名クッキー)。`remember_me` で有効期限を変えるには最大年齢を署名に含める等の工夫が要る。**この段階では `remember_me` は受けて無視(または期限延長をスコープ外)として明記**する。
- `flash` 相当はテンプレートに `error`/`message` を渡す方式に置換(refactor で)。

## 8. アプリ生成: `app/main.py`(新規)

```python
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from .config import SECRET_KEY, ENV
from .routers import login

app = FastAPI(title="light-token-server")

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=(ENV == "production"),
)
app.include_router(login.router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- CORS は `routes.py`(次段階)で設定するもの。ログインのみなら不要だが、必要なら `CORSMiddleware` をここで追加可(判断: 次段階に回す方が DRY)。
- `uvicorn app.main:app` で起動確認。

## 9. テンプレート

Bootstrap 依存を外し、プレーン + htmx 化(この段階では最小限)。

- `base.html`: 共通ヘッダ/フッタ。`{% block content %}` を持ち、`bootstrap/base.html` を extends しない。CSS/JS は本物の静的ファイル or CDN は最小に。
- `login.html`: `<form method="post" action="/login">` で `STAFFID` / `PASSWORD` 入力 + エラー表示。htmx 導入はオプション(段階 2 で `hx-post` 化)。
- `index.html`(新規): 仮リンクページ。「time-table-to-line へ」リンク → ここから `routes.py` の `/timetable/auth`(次段階)へ繋ぐ予定。ログアウトボタン(`POST /logout`)を置く。

## 10. 依存追加(manifest)

- 実装開始時に追加する依存は **`itsdangerous`**(SessionMiddleware 署名、未導入のため必須。starlette は itsdangerous を必須としていないことを確認済み)。
- 判断ポイント(パスワード)で werkzeug 維持を選ぶなら **`werkzeug`** を追加。

```bash
uv add itsdangerous
# 判断が「werkzeug 維持」の場合:
uv add werkzeug
```

- SQLite は stdlib(`sqlite3`)のみで追加不要。テストは SQLAlchemy + SQLite インメモリで動作。