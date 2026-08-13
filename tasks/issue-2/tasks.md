# Issue-2 実装タスク

実装は下記を順に、各タスクで **TDD(失敗→実装→成功→Commit)** を回す。各タスクは 2–5 分規模。

前提: 作業ディレクトリはプロジェクトルート `/home/nabu_dvl/workspace/the-calendar-to-timeline/light_token_server`。`source .venv/bin/activate` を済ませてから `uv` 系コマンドを実行する。

---

### Task 1: 設計固め(判断ポイントの利用者確認)

**Objective:** フロントへの `admin` 授受方法(Cookie クロスオリジンの扱い)とトークン有効期限を確定する。

**Files:**
- なし(ドキュメントのみ: `tasks/issue-2/overview.md` の「判断ポイント」)

**Step 1:** 利用者へ確認:
1. `admin` 授受は **オプション(A) JSON エンドポイント経由`/timetable/inquiry` に `admin` を含める)**で進めてよいか(推奨)。
2. 有効期限: アクセス **24h** / リフレッシュ **30日** でよいか。
3. `/group/all` の旧 filter 不整合を `EventORM.group_id` で**直す**方針でよいか。

**Step 2:** 確定した値を overview.md / 以降のタスクへ反映。

---

### Task 2: tokens.py(トークン発行・検証・Cookie ヘルパ)+ 失敗テスト

**Objective:** JWT(access/refresh)の payload に `admin` を含め、httpOnly Cookie ヘルパを用意する。

**Files:**
- Create: `app/tokens.py`
- Test: `tests/test_tokens.py`

**Step 1: 失敗テストを書く**

`tests/test_tokens.py`:
```python
import jwt
from app.config import SECRET_KEY
from app import tokens


def _claims(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[tokens.ALGORITHM])


def test_access_token_payload_has_admin_and_type():
    t = tokens.create_access_token(1001, 3, True)
    c = _claims(t)
    assert c["user_id"] == 1001
    assert c["group_id"] == 3
    assert c["admin"] is True
    assert c["type"] == "access"
    assert "exp" in c


def test_refresh_token_has_type_refresh():
    c = _claims(tokens.create_refresh_token(1001, 3, False))
    assert c["type"] == "refresh"
    assert c["admin"] is False
```

**Step 2: 失敗確認**
```bash
uv run pytest tests/test_tokens.py -v
```
Expected: FAIL — `ModuleNotFoundError: app.tokens`

**Step 3: `app/tokens.py` を architecture §Token のコードで作成**
(SECRET_KEY は `from .config import SECRET_KEY` を使用。有効期限は env でも可)

**Step 4: 成功確認**
```bash
uv run pytest tests/test_tokens.py -v
```
Expected: PASS(2 passed)

**Step 5: Commit**
```bash
git add app/tokens.py tests/test_tokens.py
git commit -m "feat: JWT access/refresh 発行・検証と httpOnly Cookie ヘルパ (payload に admin)"
```

---

### Task 3: timetable.py の認可依存と auth エンドポイント(/timetable/auth, /refresh)

**Objective:** `get_user_group_id`(db 引数化)と `require_token` 依存、発行/再発行エンドポイントを実装する。

**Files:**
- Create: `app/routers/timetable.py`
- Test: `tests/test_timetable.py`(auth フロー部分)

**Step 1: 失敗テスト(ログイン→ auth → httpOnly Cookie → inquiry で admin)**
```python
def _login(client):
    return client.post("/login", data={"STAFFID": "1001", "PASSWORD": "secret"}, follow_redirects=False)


def test_timetable_auth_sets_http_only_cookies(client):
    _login(client)
    r = client.get("/timetable/auth", follow_redirects=False)
    assert r.status_code == 303
    set_cookie = r.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "refresh_token=" in set_cookie
    assert "httponly" in set_cookie.lower()


def test_timetable_inquiry_requires_token(client):
    r = client.get("/timetable/inquiry", follow_redirects=False)
    assert r.status_code == 401


def test_timetable_inquiry_returns_admin(client):
    _login(client)
    client.get("/timetable/auth", follow_redirects=False)  # cookie を jar に保持
    r = client.get("/timetable/inquiry", follow_redirects=False)
    assert r.status_code == 200
    body = r.json()
    assert body["admin"] is True
    assert "staff_id" in body
```
> 注意: conftest のシードに `Team` 行が必要(下記 Task 5 で追加)。このタスクでは inquiry の `group_name` が None でもよい(team 未達のため)。team 解決は Task 5 で補完。

**Step 2: 失敗確認**
```bash
uv run pytest tests/test_timetable.py -k "auth or inquiry" -v
```
Expected: FAIL — ルーター未登録・依存未実装

**Step 3: `require_token` を `app/tokens.py` に追加し、`app/routers/timetable.py` に auth エンドポイントを実装**(architecture §Router 参照)。`/timetable/inquiry` も仮実装(team 未解決で OK)。

**Step 4: main.py にルーター未登録のため、一旦ルーター単体で確認**
`app/main.py` に `app.include_router(timetable.router)` を追加して実動作を確認(正式な CORS は Task 4)。
```bash
uv run pytest tests/test_timetable.py -k "auth or inquiry" -v
```
Expected: PASS

**Step 5: Commit**
```bash
git add app/tokens.py app/routers/timetable.py tests/test_timetable.py
git commit -m "feat: /timetable/auth, /refresh を httpOnly Cookie で実装 (require_token 依存)"
```

---

### Task 4: main.py 統合(CORS + ルーター登録)

**Objective:** `main.py` に `CORSMiddleware`(credentials 対応)と `timetable` ルーターを登録する。

**Files:**
- Modify: `app/main.py`

**Step 1: `app/main.py` を architecture §main.py のコードに更新**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import ENV, SECRET_KEY, APP_URL
from .routers import login, timetable

app = FastAPI(title="light-token-server")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY,
                   same_site="lax", https_only=(ENV == "production"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=[APP_URL, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(login.router)
app.include_router(timetable.router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

**Step 2: smoke 確認**
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Expected: 起動ログ、`/health` → `{"status":"ok"}`(Ctrl+C で停止)

**Step 3: 全テスト(現行分)が壊れていないことを確認**
```bash
uv run pytest -v
```
Expected: 既存(health + login)+ ここまでの tokens/timetable が PASS

**Step 4: Commit**
```bash
git add app/main.py
git commit -m "feat: CORS(credentials) と timetable ルーターを main に登録"
```

---

### Task 5: テスト基盤の拡充(Team / EventORM シード)+ CRUD エンドポイント移植

**Objective:** CRUD エンドポイント群を FastAPI へ移植し、SQLite シード(Team/Event)で検証可能にする。

**Files:**
- Modify: `tests/conftest.py`(Team, EventORM シード追加)
- Modify: `app/routers/timetable.py`(CRUD 移植)
- Test: `tests/test_timetable.py`(CRUD 分)

**Step 1: conftest に Team / EventORM を追加**
```python
# tests/conftest.py — db_session_factory 内に追加(Team と Event をコミット)
from app.models import StaffLogin, User, Team, EventORM
...
db.add(Team(3))  # CODE=3
from datetime import date
db.add(EventORM(staff_id=1001, group_id=3, start_time=date(2026,8,1),
                end_time=date(2026,8,1), title="t", summary=None, progress="p"))
db.commit()
```

**Step 2: 失敗テスト(CRUD)**
```python
def test_event_all(client):
    _login(client)
    client.get("/timetable/auth", follow_redirects=False)
    r = client.get("/event/all", follow_redirects=False)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_inquiry_now_has_group_name(client):
    _login(client)
    client.get("/timetable/auth", follow_redirects=False)
    r = client.get("/timetable/inquiry", follow_redirects=False)
    assert r.status_code == 200
    assert r.json()["group_name"] == "SHORTNAME_A"
```
> `Team(3)` に `NAME`/`SHORTNAME` を設定しておく(`Team.SHORTNAME`)。

**Step 3: CRUD を移植**(architecture §CRUD 表 + パターン参照)。`/event/add` はリクエスト body を Pydantic 化(`schemas.py` に `EventCreate` を追加)し、`convert_strToDate` は `app/routers/timetable.py` 内ユーティリティとして維持。

**Step 4: 成功確認**
```bash
uv run pytest tests/test_timetable.py -v
```
Expected: PASS(auth + inquiry + CRUD)

**Step 5: 全体実行**
```bash
uv run pytest -v
```
Expected: 全 PASS

**Step 6: Commit**
```bash
git add tests/conftest.py app/routers/timetable.py app/schemas.py tests/test_timetable.py
git commit -m "feat: CRUD エンドポイントを FastAPI に移植 (require_token 認可)"
```

---

### Task 6: 検証と掃除(print / 未使用・不整合の解消)

**Objective:** 移植後の品質(Flask 残存・print・未使用)を確認する。

**Step 1:** `app/` 配下に Flask 参照が残っていないか(次段階で消す対象は導入時点で確認)
```bash
grep -rn "flask\|flask_login\|flask_cors\|from . import app\|from app import app" app/ || echo "app/ に Flask 参照なし"
```
Expected: 残っていたら `timetable.py` / `tokens.py` / `main.py` 側で解消。

**Step 2:** 新規・変更ファイルに `print(` が残っていないか
```bash
grep -rn "print(" app/tokens.py app/routers/timetable.py app/main.py || echo "no stray print"
```

**Step 3:** `/event/add` のレスポンスを旧 `redirect("/event/all")` ではなく `201` + 作成物を返す等、FastAPI らしい形に整理(利用者に挙動変更を確認)。

**Step 4: Commit**(あれば)
```bash
git add app/ tests/
git commit -m "refactor: 移植後の Dead/flask 参照・print を整理"
```

---

### Task 7: 旧 Flask ファイル(routes.py / auth_middleware.py)削除

**Objective:** 移行完了を確認したうえで、旧 Flask 実装をリポジトリから除去する。

**Step 1:** `main.py` / 他モジュールがこれらを import していないことを再確認
```bash
grep -rn "routes\|auth_middleware" app/ || echo "no import of routes/auth_middleware"
```
Expected: `no import`(main.py だけが参照元になり得るが、Task 4 で `timetable` に切替済み)

**Step 2: 削除**
```bash
git rm app/routes.py app/auth_middleware.py
```

**Step 3: 全テスト**
```bash
uv run pytest -v
```
Expected: 全 PASS(import 断線なし)

**Step 4: 最終 smoke + 状態確認**
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000   # 起動確認
git status --short && git log --oneline -10
```

**Step 5: Commit**
```bash
git commit -m "refactor: Flask の routes.py / auth_middleware.py を削除 (Issue #2 完了)"
```

---

## 着手順・依存

```
Task1(設計) → Task2(tokens) → Task3(auth/refresh) → Task4(main 統合)
    → Task5(CRUD+シード) → Task6(検証・掃除) → Task7(Flask 削除)
```
- Task 1 は最初(利用者確認)。Task 2–4 は順依存。
- Task 5 は Task 3/4 の認可を土台に CRUD を足す。
- Task 7 は全テスト PASS と import 断線なしを確認してから。

## 実装時の留意(共通)

- **`uv` コマンド前は必ず `source .venv/bin/activate`**(ユーザー指示)。
- コミットは各タスク完結ごと。破壊的変更(`git rm`)は 1 タスク内に閉じる。
- DB アクセスは必ず `db: Session = Depends(get_db)`(SessionLocal 直参照禁止)。
- `raise RedirectResponse` は使わず `HTTPException(303, headers=...)` か、FastAPI の `RedirectResponse` は **依存内での raise でなく return** で使う(Starlette 1.4 制約)。
- JWT payload の既存キー(`user_id`,`group_id`)は維持し、`admin` を追加(メソッド名変更は OK)。
- Flask の `db.session` 参照・`current_user`・`token_required` デコレータは使わない。
