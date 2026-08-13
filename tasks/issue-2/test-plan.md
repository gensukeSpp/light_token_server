# Issue-2 テスト計画 — Access Token / CRUD 移行

## 方針
- 自動テストは **SQLite インメモリ**(`poolclass=StaticPool` + `check_same_thread=False`)で実施。実 DB 不要。
- 既存の `tests/conftest.py`(`get_db` 上書き + `User(1001)` / `StaffLogin(1001,"secret",True)` シード)を拡張し、`Team` / `EventORM` シードを追加。
- トークン検証は PyJWT で直接 decode して payload(`admin` 等)を確認 + TestClient の Cookie jar でエンドツーエンド確認。

## テスト対象・期待結果

### tests/test_tokens.py(新規)— トークン単体
| テスト | 期待 |
| :--- | :--- |
| `test_access_token_payload_has_admin_and_type` | `user_id`/`group_id`/`admin`/`type="access"`/`exp` を含む |
| `test_refresh_token_has_type_refresh` | `type="refresh"`、`admin` が入る |
| (任意)`test_expired_token_rejected` | 期限切れトークンで `decode_token` が 401 を raise |

### tests/test_timetable.py(新規)— エンドツーエンド
| テスト | 期待 |
| :--- | :--- |
| `test_timetable_auth_sets_http_only_cookies` | ログイン後 `/timetable/auth` で 303 + `Set-Cookie` に `access_token` / `refresh_token` と `httponly` |
| `test_timetable_inquiry_requires_token` | 未認証 `/timetable/inquiry` → 401 |
| `test_timetable_inquiry_returns_admin` | 認証後 `/timetable/inquiry` → 200 + `admin=True` |
| `test_refresh_issues_new_access_token` | `/refresh` で新しい `access_token` Cookie を発行 |
| `test_event_all` | 認証後 `/event/all` → 200 で一覧 |
| `test_group_users` | 認証後 `/group/users` → 同チームメンバー |
| `test_group_names` | 認証後 `/group-names` → `SHORTNAME` 一覧 |
| `test_event_add` | `POST /event/add` → 作成されたことを確認 |
| `test_event_update` | `POST /event/update/{id}` → `summary`/`progress` 更新を確認 |
| `test_event_remove` | `DELETE /event/remove/{id}` → 削除を確認 |

### 既存(回帰)— tests/test_health.py, tests/test_login.py
- 変更後も PASS を維持(login フローに影響を与えないこと)。

## 実行コマンド
```bash
source .venv/bin/activate
uv run pytest tests/test_tokens.py -v
uv run pytest tests/test_timetable.py -v
uv run pytest -v            # 全体
```

## 検証ポイント
1. JWT payload に **`admin`**(`StaffLogin.ADMIN`)が含まれる。
2. access / refresh の両方が **httpOnly Cookie** で発行・更新される。
3. 保護付きエンドポイントは **未認証で 401**、トークン有効時のみ 200。
4. 既存のログイン・ヘルス回帰が壊れない。
5. `app/` 配下から Flask 参照・`print()`・未使用が消えている(Task 6 の grep)。

## 手動 QA(利用者実施)
- バックエンド(`uvicorn app.main:app`)とフロント(`cd ../time-table-to-line`)を起動し、ログイン → アクセストークン発行 → フロントで `admin: boolean` が正しく渡ることを確認。
- Cookie が httpOnly で保存されていることをブラウザ DevTools で確認。
