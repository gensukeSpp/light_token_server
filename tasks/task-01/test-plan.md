# Task-01 テストプラン

## 方針

- **テスト対象:** FastAPI ログインフロー(`/login`, `/logout`, `/`)。
- **DB:** SQLite インメモリ + `get_db` 依存の差し替え。→ 実 PostgreSQL が未移行でもロジックを自動検証可能。
- **HTTP クライアント:** starlette 同梱 `TestClient`(httpx ベース、`uv run pytest` で動く)。
- **TDD:** 各ファイルは先に失敗テスト → 実装 → 成功。

## テスト構成

```
tests/
  conftest.py      # SQLite engine, StaffLogin シード, TestClient(client), get_db 上書き
  test_health.py   # Task2: /health
  test_login.py    # Task8: ログインフロー統合
```

## conftest の責務

1. `create_engine("sqlite://", connect_args={"check_same_thread": False})` を生成
2. `Base.metadata.create_all(engine)` で旧スキーマ(M_STAFFINFO / M_LOGGININFO / M_TEAM / T_TIMELINE_EVENT)を作成
3. テスト用スタッフを 1 件シード(例: `STAFFID=1001`, `PASSWORD_HASH=<目的の方式で "secret">`, `ADMIN=True`)
   - パスワードハッシュの作り方は実装決定(werkzeug/passlib)に合わせる(下記「実装との連動」)
4. `app.dependency_overrides[get_db]` で SQLite セッションを返す
5. `TestClient(app)` を `with` で yield(設定・破棄を確実に)

## テストケース一覧

### `tests/test_health.py`(Task 2)
| # | ケース | 期待 |
|---|--------|------|
| 1 | `GET /health` | `200`, `{"status":"ok"}` |

### `tests/test_login.py`(Task 8)
| # | ケース | 準備 | 期待 |
|---|--------|------|------|
| 1 | ログインページ表示 | 未ログイン | `GET /login` → `200`, html |
| 2 | 正資格でログイン | シード済み | `POST /login` data=`STAFFID=1001,PASSWORD=secret` → `302/303`, `Location` に `/`, レスポンス `set-cookie` に `httponly` かつ `session=` |
| 3 | 誤パスワード | シード済み | `POST /login` data=`PASSWORD=wrong` → `400`, 本文にエラー文言 |
| 4 | 未ログインで `/` | 未ログイン | `GET /` → `302/303`, `Location` に `/login` |
| 5 | ログアウトでセッション消失 | ログイン済み → `POST /logout` | `302/303` → 直後 `GET /` が `302/303`(再ログイン要求) |

## httpOnly / セッションの検証ポイント

- `SessionMiddleware` は署名クッキーを既定で `httpOnly=True` で設定する。テストは `set-cookie` ヘッダに `httponly` を含むことを確認する(セキュリティ要件: httpOnly セッションクッキー)。
- +α(任意): クッキーが `Secure` / `SameSite` 設定になるのは `ENV=production` 時のみ。テストでは development 前提のため確認対象外。

## 実装との連動(実装タスクで必ず揃えること)

1. **セッションアクセス経路の一元化**: ルーター/security で `SessionLocal()` を**直接**使わず、必ず `get_db` 依存(または共通ヘルパー)経由にする。そうしないと `dependency_overrides` による SQLite 差し替えが効かず、テストが実 DB を叩いてしまう。
   - 修正案: `security.login_required` と `routers/login.py` のクエリを、`db: Session = Depends(get_db)` で受けて使う形に統一する。→ テストが短く確実になる。
2. **パスワード検証**: `StaffLogin.check_password` をテスト用シードのハッシュと一致させる。werkzeug 維持なら `generate_password_hash("secret")` を conftest でも使う。
3. **リダイレクトのステータス**: 308/307 でなく `302/303` を使う(ブラウザ・TestClient 双方で safety な redirect)。テスト期待値は `302/303` の許容。
4. **フォーム受け取り**: `POST /login` は `application/x-www-form-urlencoded`(Form)で送る。`python-multipart` が必須(マニフェスト済み)。

## 検証コマンド

```bash
# 単体
uv run pytest tests/test_login.py -v
uv run pytest tests/test_health.py -v
# 全体
uv run pytest -v
# 実 DB が不要でも通過することを明示(ヘルス含め全 PASS が完了条件)
```

## 完了条件(Definition of Done)

- `uv run pytest -v` が全 PASS(ヘルス + ログインフロー)
- `uvicorn app.main:app` で起動し、`/health` が `{"status":"ok"}` を返す
- ログインアクセス経路が `get_db` 依存に一元化され、テストで実 DB に依存しない
- Flask 参照が新コード(`main.py`,`routers/`,`schemas.py`,`security.py`)から消えている(`routes.py`/`auth_middleware.py` は次段階スコープなので対象外)