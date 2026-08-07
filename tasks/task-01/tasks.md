# Task-01 実装タスク

実装は下記を順に、各タスクで **TDD(失敗→実装→成功→Commit)** を回す。各タスクは 2–5 分規模。

前提: 作業ディレクトリはプロジェクトルート `/home/nabu_dvl/workspace/the-calendar-to-timeline/light_token_server`。`source .venv/bin/activate` を済ませてから `uv` 系コマンドを実行する。

---

### Task 1: 追加依存(itersdangerous / 判断で werkzeug)を manifest に宣言

**Objective:** セッション署名と(判断に応じて)パスワード検証に必要な依存を追加する。

**Files:**
- Modify: `pyproject.toml` / `uv.lock`

**Step 1:**
```bash
uv add itsdangerous
# 「werkzeug 維持」を選んだ場合のみ:
uv add werkzeug
```

**Step 2:** 検証
```bash
uv pip list | grep -iE 'itsdangerous|werkzeug'
```

**Step 3:** Commit
```bash
git add pyproject.toml uv.lock
git commit -m "chore: セッション署名に itsdangerous を追加"
```
(werkzeug 追加時は `-m "chore: パスワード検証に werkzeug を追加"` を分けて commit)

---

### Task 2: 失敗テスト(インフラ) — SQLite conftest とヘルスチェック

**Objective:** テスト用の最小基盤(TestClient + SQLite + /health)を TDD で作る。

**Files:**
- Test: `tests/conftest.py`, `tests/test_health.py`

**Step 1: テストを書く(failing)**

`tests/test_health.py`:
```python
from fastapi.testclient import TestClient  # starlette 同梱

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

`tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
```

**Step 2: 失敗確認(まだ app.main が無い)**
```bash
uv run pytest tests/test_health.py -v
```
Expected: FAIL — `ModuleNotFoundError: app.main`

**Step 3: 最小実装 `app/main.py`**(health のみ、この時点で `app/__init__.py` も作成)
- Create: `app/__init__.py`(空)
- Create: `app/main.py`
```python
from fastapi import FastAPI

app = FastAPI(title="light-token-server")

@app.get("/health")
def health():
    return {"status": "ok"}
```

**Step 4: 成功確認**
```bash
uv run pytest tests/test_health.py -v
```
Expected: PASS(1 passed)

**Step 5:** Commit
```bash
git add tests/ app/__init__.py app/main.py
git commit -m "feat: FastAPI アプリ基盤と /health (TDD)"
```

---

### Task 3: config / database_base を PostgreSQL 接続 + get_db に

**Objective:** 接続設定を env から組み、`get_db` 依存を用意する(models の import を壊さない)。

**Files:**
- Create: `app/config.py`
- Modify: `app/database_base.py`

**Step 1: `app/config.py` 作成**(architecture §2 のコード)
**Step 2: `app/database_base.py` 編集**(architecture §3 のコード。URL を psycopg に、`get_db` 追加。`Base` は維持)

**Step 3: 成功確認(import が壊れていないこと)**
```bash
uv run python -c "from app.database_base import Base, get_db; from app.models import StaffLogin, User, Team, EventORM; print('ok')"
```
Expected: `ok`(この時点で実 DB 接続はしない)

**Step 4:** Commit
```bash
git add app/config.py app/database_base.py
git commit -m "feat: PostgreSQL 接続設定と get_db 依存"
```

---

### Task 4: Pydantic フォーム(schemas.py)と旧 form.py 削除

**Objective:** Flask-WTF 依存を消し、Pydantic フォームに置換する。

**Files:**
- Create: `app/schemas.py`
- Delete: `app/form.py`

**Step 1: `app/schemas.py` 作成**(architecture §5 の `LoginForm`)

**Step 2: 検証**
```bash
uv run python -c "from app.schemas import LoginForm; f=LoginForm(STAFFID=1, PASSWORD='x'); print(f)"
```
Expected: `STAFFID=1 PASSWORD='x' remember_me=False`

**Step 3: `git rm app/form.py`**
**Step 4:** Commit
```bash
git add app/schemas.py && git rm app/form.py
git commit -m "refactor: フォームを Pydantic (schemas.py) へ、form.py を削除"
```

---

### Task 5: security.py(login_required 依存)

**Objective:** セッションからログインユーザーを解決する依存を用意する。

**Files:**
- Create: `app/security.py`

**Step 1:** architecture §6 のコードで `app/security.py` を作成

**Step 2: 検証**
```bash
uv run python -c "from app.security import login_required; print('ok')"
```

**Step 3:** Commit
```bash
git add app/security.py
git commit -m "feat: セッションベースの login_required 依存"
```

---

### Task 6: ルーター login.py(ログイン・ログアウト・リンクページ)

**Objective:** `/login`(GET/POST)、`/logout`(POST)、`/`(リンクページ、要ログイン)を実装する。

**Files:**
- Create: `app/routers/__init__.py`(空)
- Create: `app/routers/login.py`(architecture §7)
- Delete: `app/login.py`(旧 Flask)

**Step 1:** `app/routers/login.py` を architecture §7 のコードで作成
**Step 2:** `git rm app/login.py`
**Step 3: 検証(ルーター modules が import できる)**
```bash
uv run python -c "from app.routers import login; print(list(login.router.routes))"
```
Expected: 4 ルート(`/login` GET/POST, `/logout` POST, `/` GET)

**Step 4: 実装本体の動作確認は Task 8 のテストで行う**(router を先に main に登録しないと実動作しない)
**Step 5:** Commit
```bash
git add app/routers/ && git rm app/login.py
git commit -m "feat: FastAPI ログイン/ログアウト/リンクページ (Flask login.py を置換)"
```

---

### Task 7: main.py に SessionMiddleware + ルーター登録 + テンプレ更新

**Objective:** ログインが実際に動くよう main を仕上げ、Bootstrap 依存テンプレを書き換える。

**Files:**
- Modify: `app/main.py`
- Write: `app/templates/base.html`(書き換え), `app/templates/login.html`(書き換え), `app/templates/index.html`(新規)

**Step 1: `app/main.py` を architecture §8 に**: `SessionMiddleware` 追加 + `include_router(login.router)`

**Step 2: テンプレ更新**
- `base.html`: `{% block content %}` のみの最小構成(extends しない)
- `login.html`: `<form method="post" action="/login">`、`<input name="STAFFID">` / `<input type="password" name="PASSWORD">`、`{{ error }}` 表示
- `index.html`: 「time-table-to-line へ」リンク + `<form method="post" action="/logout">` + ログイン中ユーザー表示

**Step 3: 実動作の smoke(サーバー起動)**
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Expected: 起動ログ、`/health` → `{"status":"ok"}`(Ctrl+C で停止)

**Step 4:** Commit
```bash
git add app/main.py app/templates/
git commit -m "feat: SessionMiddleware とテンプレの Bootstrap 廃止 (htmx 化基盤)"
```

---

### Task 8: ログインフロー統合テスト(本命)

**Objective:** ログイン→ httpOnly セッションクッキー → リンクページ、失敗系を SQLite で自動検証する。

**Files:**
- Test: `tests/test_login.py`
- Modify: `tests/conftest.py`(SQLite engine + シード + get_db 上書き)

**Step 1: conftest を SQLite 対応に**

`tests/conftest.py`(改訂):
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database_base import Base, get_db
from app.main import app
from app.models import StaffLogin

@pytest.fixture
def db_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(StaffLogin.__table__.insert(), {
            "id": 1, "STAFFID": 1001, "PASSWORD_HASH": _hash("secret"),
            "ADMIN": True})
    return engine

# パスワードハッシュ生成は実装の方式(wergzeug/passlib)に合わせる
def _hash(p):  # 実装タスクで確定
    ...

@pytest.fixture
def client(db_engine):
    session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    def override_get_db():
        db = session()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

※ 注意: この conftest は `get_db` をルーター/security が使う前提。ルーターで `SessionLocal` を直接使う作り(architecture §7)の場合は、**直接の `SessionLocal()` を依存 `get_db` 経由に統一する**必要がある(DRY かつテスト差し替え可能のため)。実装時にこの 2 経路を一本化すること。

**Step 2: テストを書く**
`tests/test_login.py`:
```python
def test_login_page_get(client):
    r = client.get("/login")
    assert r.status_code == 200

def test_login_success_sets_session(client):
    r = client.post("/login", data={"STAFFID": "1001", "PASSWORD": "secret"})
    assert r.status_code in (302, 303)
    assert "/" in r.headers["location"]
    set_cookie = r.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()  # httpOnly
    assert "session=" in set_cookie

def test_login_wrong_password(client):
    r = client.post("/login", data={"STAFFID": "1001", "PASSWORD": "wrong"})
    assert r.status_code == 400
    assert "違います" in r.text

def test_index_requires_login(client):
    r = client.get("/")
    assert r.status_code in (302, 303)
    assert "/login" in r.headers["location"]

def test_logout_clears_session(client):
    client.post("/login", data={"STAFFID": "1001", "PASSWORD": "secret"})
    r = client.post("/logout")
    assert r.status_code in (302, 303)
    r2 = client.get("/")
    assert r2.status_code in (302, 303)  # 再ログイン要求
```

**Step 3: TDD 実行**
```bash
uv run pytest tests/test_login.py -v
```
- 最初は FAIL(例: SessionLocal 直参照で auth が効かない、cookie 名違い等)→ 実装をルーター/security のセッション経由へ揃えて PASS に
Expected: 5 passed(見出しの httpOnly・リダイレクト・400 失敗・ログイン必須・ログアウト)

**Step 4: 全体実行**
```bash
uv run pytest -v
```
Expected: 全 passed(health + login)

**Step 5:** Commit
```bash
git add tests/
git commit -m "test: ログインフロー統合テスト (SQLite / httpOnly セッション)"
```

---

### Task 9: 最終検証(スコープ: マニフェスト & ログイン)

**Objective:** この段階の完了条件とスコープ違反(Flask 残存)を確認する。

**Step 1:** 全テスト通過
```bash
uv run pytest -v
```

**Step 2:** Flask が実コードから import されていないか(次段階スコープ分は除く)
```bash
grep -rn "flask\|wtforms\|flask_login\|flask_cors\|flask_sqlalchemy" app/ || echo "app/ に Flask 参照なし"
```
- `routes.py` / `auth_middleware.py` は**次段階**なのでここでは無視(OK とする)。ただし `main.py` がこれらを import していないことを確認する。

**Step 3:** ゴミ(print コメント)を削れているか該当箇所を確認
```bash
grep -rn "print(" app/ | grep -v "routers\|main" || echo "no stray print in new code"
```
(実装した新ファイル内に `print()` が残っていたら除去)

**Step 4: 最終 commit** 状態を確認
```bash
git status --short && git log --oneline -10
```

## 着手順・依存

```
Task1(deps) → Task2(基盤) → Task3(config/db) → Task4(schemas)
            → Task5(security) → Task6(ルーター) → Task7(main+tmpl)
            → Task8(統合テスト) → Task9(検証)
```

- Task 1 は最初。Task 2–7 はおおよそ順依存(Task 7 が実動に必要なラストピース)。
- Task 8 の統合テストは Task 6/7 の実装を検証するため最後。必要なら Task 6/7 の後にサンドイッチして書いても良い(実装上は TDD 順を守る)。

## 実装時の留意(共通)

- **`uv` コマンド前は必ず `source .venv/bin/activate`**(ユーザー指示)。
- コミットは各タスク完結ごと。破壊的変更(`git rm`)は 1 タスク内に閉じる。
- 旧 Flask の `flash` / `url_for` 相当はテンプレート引数方式へ置換。
- `routes.py` / `auth_middleware.py` は**触らない**(本タスク対象外)。ただし `main.py` が誤って import しないよう注意。