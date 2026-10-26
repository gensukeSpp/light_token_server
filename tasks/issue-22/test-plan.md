# Issue-22 テスト計画 — `/event/add` の staff_id 照合

## 1. 目的

Issue #22 の受け入れ条件を API テストで固定し、回帰を防ぐ。
テストは `tests/test_timetable.py` に Issue #20 セクションの後続として追加する（新規ファイルは作らない）。

## 2. テスト環境

- SQLite インメモリ + StaticPool + `get_db` override（`tests/conftest.py`、既存のまま）
- 認証: `tokens.create_access_token(user_id, group_id, admin)` による **Bearer 直接生成**
  （cookie ログイン非依存。`test_milestone.py` のコメントに「cookie セッション確立は環境依存で不安定」とある
  ため、`test_timetable.py` の Issue #20 セクションと同じ方式を踏襲）
- 投入データ: conftest で `StaffLogin(1001, secret, True)`（admin）/ `StaffLogin(1002, secret, False)`（非 admin）、
  イベント 1 件（staff_id=1001）が事前投入済み

## 3. テストマトリクス

| # | テスト名 | 前提 claims | body.staff_id | 期待 | 対応する受入条件 |
|---|---|---|---|---|---|
| 1 | `test_event_add_self_non_admin_allowed` | 1002 / non-admin | 1002（本人） | **201** + staff_id=1002 | 受入 1 |
| 2 | `test_event_add_other_member_forbidden_for_non_admin` | 1002 / non-admin | 1001（他人） | **403** + 一覧に混入しない（件数・名義とも不変） | 受入 2 |
| 3 | `test_event_add_admin_can_create_for_others` | 1001 / admin | 1002（他人） | **201** + staff_id=1002 | 受入 3 |
| 4 | `test_event_add_nonexistent_staff_forbidden_for_non_admin` | 1002 / non-admin | 9999（不明 ID） | **403** | エッジ（受入 2 の拡張） |

## 4. 回帰対象（既存テストが壊れないことの確認）

| 既存テスト | 経路 | 新実装での期待 | 確認方法 |
|---|---|---|---|
| `test_timetable.py::test_event_add` | admin（1001, True）が staff_id=1001 | 201（許可） | `pytest tests/test_timetable.py -v` 全体 |
| `test_timetable.py::_add_event_staff`（issue-20 ヘルパー） | admin が任意 staff_id | 201（許可） | issue-20 セクション 7 件が通ること |
| `test_milestone.py::_add_event`（ヘルパー） | admin（1001, True）が staff_id=1001 | 201（許可） | `pytest tests/test_milestone.py -v` |

## 5. 実施コマンド

```bash
# 前提: .venv 活性化を忘れない
source .venv/bin/activate

# Task 2: RED 確認（新規 4 件のうち 2 件が失敗するはず）
uv run pytest tests/test_timetable.py -k "event_add" -v

# Task 4: GREEN 確認（実装後、4 件全て PASS）
uv run pytest tests/test_timetable.py -k "event_add" -v
uv run pytest tests/test_timetable.py -v

# Task 5: 全回帰（milestone 経由の /event/add を含む）
uv run pytest tests/test_milestone.py -v
uv run pytest -q
```

## 6. 期待結果

- 実装後: `tests/test_timetable.py` 全 PASS（従来 14 件 + issue-20 7 件 + 新規 4 件 相当）
- 全体: `uv run pytest -q` → 全 PASS（現行 87 + 4 = 91 passed 相当、FAIL 0）
- `test_milestone.py` は無影響（60 件強、全て PASS のまま）

## 7. 検証のポイント（レッドの正しさ）

- Task 2 で失敗するのは **403 を期待して 201 を受ける 2 件**のみであること。
- もし `test_event_add_self_non_admin_allowed` や `test_event_add_admin_can_create_for_others` も失敗するなら、
  テストの前提（claims の生成・エンドポイント・JSON キー）が誤っている可能性があるため、その場合は先に
  fixture / トークン生成を確認する（実装に入る前に対処）。
