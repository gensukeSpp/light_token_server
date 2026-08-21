# Task-03 テストプラン — /milestone/* API

## 方針

- **テスト対象:** `POST /milestone/add` `GET /milestone/all` `POST /milestone/update/{id}` `DELETE /milestone/remove/{id}`、および既存 `/event/add` `/event/update/{id}` への milestone_id / completed 反映。
- **DB:** SQLite インメモリ + `get_db` 依存の差し替え(既存 `tests/conftest.py` を再利用)。→ 実 PostgreSQL が未移行でもロジックを自動検証可能。
- **HTTP クライアント:** starlette 同梱 `TestClient`(httpx ベース、`uv run pytest` で動く)。
- **認証:** 既存 `tests/test_timetable.py` のセッションクッキーまわり 10 件が**ベースから既に失敗**しているため、それに影響されないよう **Bearer トークンを直接生成して送る方式**で認可を通す。
- **TDD:** 先に失敗テスト(red)→ 実装 → 成功(green)。

## テスト構成

```
tests/
  conftest.py        # 既存(SQLite StaticPool + get_db 上書き + シード)。再利用
  test_milestone.py  # 新規: /milestone/* 統合
```

## 認可ヘルパー(ファイル冒頭)

```python
import jwt
from app import tokens

def _bearer(admin: bool = True) -> dict:
    access = tokens.create_access_token(1001, 3, admin)  # staff_id=1001, group=3, admin
    return {"Authorization": f"Bearer {access}"}
```

- `tests/conftest.py` がシードする `StaffLogin(1001, "secret", True)` と一致させる(STAFFID=1001, group=3, admin=True)。
- 非 admin ケースは `tokens.create_access_token(1001, 3, False)` で生成。

## テストケース一覧

### `tests/test_milestone.py`

| # | ケース | 準備 | 期待 |
|---|--------|------|------|
| 1 | マイルストーン追加(admin) | admin Bearer | `POST /milestone/add` `{title:"M1"}` → `201`、返り値 `color in MILESTONE_COLORS`, `status==True`, `staff_id==1001` |
| 2 | 色衝突回避 | 1 件作成済み | 2 件目 `POST/milestone/add` → `201`, 2 件目の `color=="#009688"`(MILESTONE_COLORS[1]、1 件目が `#9c27b0` のとき) |
| 3 | open 一覧 | 1 件追加 | `GET /milestone/all` → `200`, リスト長 1, 各要素に `title` `color` `status` |
| 4 | 追加(非 admin) | 非 admin Bearer | `POST /milestone/add` → `403` |
| 5 | close(達成日入力) | open 1 件 + 子イベント 1 件 | `POST /milestone/update/1` `{accomplished_date:"2026-08-20"}` → `200`, `status is False`, 子イベント `completed is True` |
| 6 | close 済みを再度 | status=False 済み | `POST /milestone/update/1` → `409` |
| 7 | 存在しない id | なし | `POST /milestone/update/999` → `404` |
| 8 | 削除(admin) | マイル + 子イベント | `DELETE /milestone/remove/1` → `200` `{"deleted":1}`, 子イベントの `milestone_id` が `None` |
| 9 | /event/add に milestone_id | マイル 1 件 + admin | `POST /event/add` `{..., milestone_id:1}` → `201`, 返り `to_dict` に `milestone_id==1` |
| 10 | /event/update に completed | `POST /event/update/1` `{completed:true}` → `200`, `to_dict` の `completed is True` |

※ 危いつら: 色の具体値はパレット定義に依存する。`MILESTONE_COLORS` の順序(AGENTS.md / requirement-03.md 準拠)をテスト内で import して検証するのが安全:
```python
from app.routers.timetable import MILESTONE_COLORS
# 期待 color == MILESTONE_COLORS[1] 等の形で検証
```
こうすればパレット定義とテストがズレない。

## チェックすべきバリデーション・境界

- **admin 判定:** `claims["admin"]` が False / 欠如 → 403。Bearer を作らず送らないケース → 401(既存 require_token)。
- **status 遷移**: open(status=True)→ close(status=False)。close 済みを再度 update → 409(再 open 不可)。
- **子イベント連動**: close 時は全子イベント `completed=True`、削除時は全子イベント `milestone_id=None`。
- **色**: 閉じたマイルストーンの色は次の add で再利用可(open 中のみ占有)。
- **10 件超え**: 全部使用中なら先頭から cyclic(単体ユニットテストで `_next_color` を直接呼ぶのも可)。

## httpOnly / トークンの検証ポイント

- 認証は既存 `require_token` をそのまま使う。Bearer ヘッダーで送ったアクセストークンが通ることを、`test_bearer_header_only_*` と同様に確認する。
- このテストではセッション cookie に依存しない(既存 test_timetable の失敗と独立)。

## 実装との連動(実装タスクで必ず揃えること)

1. **色ヘルパーのテスト容易性**: `_next_color` をモジュール関数として `app/routers/timetable.py` に置き、`MILESTONE_COLORS` とセットで import できるようにする(関数がルーター内に直書きされると Unit テスト不可)。
2. **radmin 判定の統一**: 作成/close/削除の全エンドポイントで `if not claims.get("admin"): raise HTTPException(403, ...)` に統一する(DRY)。専用デコレータを作るのは後続リファクタ枠で可。
3. **`.` status クエリ**: open 判別は `MilestoneORM.status.is_(True)` を使う(bool 比較の安定性)。`.filter(MilestoneORM.status == True)` でも可。
4. **close 連動の一括更新 / 逐次更新**: 実装は分りやすさ優先で子イベントをループで回して `completed=True` にする(件数が少数だから)。件数が多い場合の一括 `update()` 化は後続で検討。

## 検証コマンド

```bash
# 単体
uv run pytest tests/test_milestone.py -v
# 全体(既存 test_timetable の既知 10 失敗はベース由来・本タスク起因でない)
uv run pytest -q
```

## 完了条件(Definition of Done)

- `uv run pytest tests/test_milestone.py -v` が全 PASS。
- 既存(new/health/login/tokens)が新たに壊れていない(ベース状態と同等 or 改善)。
- `uvicorn app.main:app` 起動確認(任意・マイルストーンは JSON API のため UI 確認は Web で実施可能)。
- 既存 `test_timetable` の既知 10 失敗を**本タスクで直さない**(別 Task)。