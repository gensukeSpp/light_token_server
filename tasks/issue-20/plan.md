# Issue #20 実装計画 — イベント更新・削除への所有者チェック追加（admin は例外）

**Goal:** `/event/update/{id}` と `/event/remove/{id}` に「本人 or admin のみ」の権限チェックを追加し、
`/date/update` の所有者チェックと同一のポリシーに統一する。閲覧緩和（PR #45）で他メンバーのイベント ID を
見られるようになったことから、API 直叩きで他人のイベントを更新・削除できる既存欠陥を塞ぐ。

**参照:** Issue #20 / フロント PR #45（time-table-to-line）レビュー [Medium] 指摘 2。

**要件（ユーザー決定）:** 個別ユーザーのイベントの更新・削除はユーザー本人のみの操作であるため、
**admin は例外**（admin は誰のイベントも更新・削除可）。

**Tech Stack:** FastAPI / SQLAlchemy 2 / pytest（SQLite in-memory StaticPool + get_db override）/ uv + venv。

## 1. 現状（読み取ったコード・ベースライン）

- `app/routers/timetable.py:193-217` `update_event_item`
  - `require_token` のみ。`target` 取得後 404 チェックだけ行い、`staff_id` の所有者チェック無し。
  - `body.summary / body.progress / body.milestone_id / body.completed` を上書きし `to_dict()` を返す。
- `app/routers/timetable.py:246-257` `remove_event_item`
  - `require_token` のみ。404 チェック後に無条件で `db.delete(target)`。
- `app/routers/timetable.py:220-243` `update_event_dates`（`/date/update`）
  - **所有者チェック済み**（234-238 行）: `if target.staff_id != claims.get("user_id"): raise 403`。
  - ただし **admin 例外が無い**（現状 admin でも他人のイベントを動かせない）。
- claims の形状（`app/tokens.py:29-33,114`）: `claims["user_id"]`, `claims["admin"]`（bool）が常に存在。
- `EventCreate`（`app/schemas.py:12`）は `staff_id: int` を受ける → テストで「他人所有イベント」を
  `POST /event/add` 経由で任意 staff_id で作成できる。
- テスト: `tests/test_timetable.py`。イベント 1 件（`staff_id=1001`）が conftest で事前投入済み。
  トークンは `tokens.create_access_token(user_id, group_id, admin)` で任意生成可能。
  - `test_event_update` / `test_event_remove` / `test_event_update_progress_null_clears` / `test_date_update_*` は
    いずれも**本人かつ admin（1001, True）** で実行 → 新しい「本人 or admin」チェックでも全て成功のまま。
- ベースライン: `source .venv/bin/activate && python -m pytest -q` → **79 passed, 1 warning**。

## 2. 方針（決定事項）

1. **ポリシーを 1 つに統一する**: 更新・削除は「イベントの作成者本人」または「admin」のみ許可。
   - `if target.staff_id == claims.get("user_id")` → 許可
   - `elif claims.get("admin")` → 許可
   - `else` → `HTTPException(403, "not allowed to modify other member's event")`
2. **DRY**: 判定をモジュール内プライベート関数 `_require_event_owner_or_admin(target, claims)` に集約し、
   `update_event_item` / `remove_event_item` / `update_event_dates` の 3 箇所から呼ぶ。
   - `update_event_dates` にも admin 例外を追加し、3 エンドポイントの挙動を揃える
     （ユーザー要件「admin は例外」の帰結。動作は「緩和」方向のみで既存テストは壊れない）。
3. **404 の優先**: 存在しないイベントは現状どおり先に `HTTPException(404)` を返す
   （存在確認と権限判定の順序は変えない）。
4. **フロント / 認証契約の変更なし**: 権限制御は backend 側で完結。Authorization ヘッダー・Cookie の両対応はそのまま。
5. コミットは本 Issue の必須作業としない（issue-16 と同じ取り決め）。`tasks/` は git 管理下。

## 3. 変更ファイル

| 種別 | パス | 内容 |
|---|---|---|
| Modify | `app/routers/timetable.py:193-257` | `_require_event_owner_or_admin()` 追加、update / remove / date.update の 3 箇所に呼び出し追加 |
| Modify | `tests/test_timetable.py`（末尾） | 403 / 本人・非 admin 成功 / admin 例外のテストを追加 |

※ `app/tokens.py` の既存 `print(...)` は本 Issue のスコープ外（別途 backend 整理時に扱う）。
※ 呼び出し側 フロント（time-table-to-line）は変更不要（UI 側は既に isOwnEvent で管理済み、backend が保険を掛ける）。

## 4. タスク概要

詳細は `tasks.md` に分割して記載（各 2–5 分・TDD）。

- **Task 1**: `update_event_item` の権限テストを追加（他人→403 / 本人・非 admin→200 / admin・他人→200）→ RED
- **Task 2**: ヘルパー `_require_event_owner_or_admin` 追加 + `update_event_item` へ適用 → GREEN
- **Task 3**: `remove_event_item` の権限テスト追加（他人→403 / 本人・非 admin→200 / admin・他人→200）→ RED
- **Task 4**: `remove_event_item` へ適用 → GREEN
- **Task 5**: `update_event_dates` に admin 例外を追加（他メンバー→403 の維持 + admin 成功のテスト追加）→ RED→GREEN
- **Task 6**: 全体検証（`pytest -q` 全 passed）、`git status` で影響ファイル確認、受け入れ条件の突き合わせ

## 5. 検証

```bash
cd /home/nabu_dvl/workspace/the-calendar-to-timeline/light_token_server
source .venv/bin/activate
python -m pytest tests/test_timetable.py -q   # 新規テストが通る
python -m pytest -q                            # 全 79 + 追加分がグリーン
```

## 6. リスク / 補足 / 未決事項

- **破壊的変更の有無**: 既存の本人・admin 操作は全て許可のまま → 通常ユーザーの動作は変わらない。
  権限の無い不正アクセスだけが 403 になる。（外部クライアントで「他メンバーのイベントを無断更新」していた
  ケースは元々想定外であり、今回で正しく拒否される。）
- **`/date/update` の緩和**: 現状は「本人のみ」で admin 例外が無いが、ユーザー要件（admin は例外）に合わせ
  3 エンドポイントを揃える。これは**権限を緩める**方向の変更で、既存テストは壊れない。
- **判定順**: 404 → 403 の順。イベント存在の隠蔽を意図しない（権限制御が目的）。
- **エラーメッセージ**: `/date/update` の既存文言「not allowed to update other member's event」を
  共通ヘルパーの「not allowed to modify other member's event」に統一する（テストで文言固定していないため安全）。
- **未決事項**: なし（ユーザー要件により admin 例外は確定）。