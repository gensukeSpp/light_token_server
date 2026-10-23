---
created: 2026-10-23T11:00:42+09:00
updated: 2026-10-23T11:00:42+09:00
---

# Issue #20 — イベント更新・削除への所有者チェック追加（本人 or admin）

> 対象差分: ブランチ `fix/front-review/45-m-2` の作業ツリー（`origin/main` 起点）
> 本ファイルは Issue #20 で発生した**変更内容（差分）の記録**であり、機能ごとの現行契約の正本ではない。
> マイルストーン関連の現行契約は `specs/2026-10-13-milestone-event-retrieval-spec.md`（正本）を参照。
> **イベント更新・削除の権限契約は `.hermes/rules/milestones.md` の Permission model / API endpoints に追記済み。**
> 変更の入力: フロント PR `gensukeSpp/time-table-to-line` PR #45 レビュー [Medium] 指摘 2 / ユーザー要件（admin は例外）

---

## 1. 変更の背景・動機

閲覧緩和（PR #45）により他メンバーのイベント ID を閲覧できるようになったため、API を直接叩くと
認証済みの任意ユーザーが**他人のイベントを更新・削除できる**既存欠陥が顕在化した。一覧（`/event/all`）等で
ID を取得した後、`/event/update/{id}` や `/event/remove/{id}` に他者の ID を渡せば権限なく改変できていた。

| # | 指摘 | 内容 | 対応 |
|---|---|---|---|
| 1 | [Medium] 指摘 2 | `update_event_item`（218 付近）と `remove_event_item`（246 付近）は `require_token` のみで `staff_id` の所有者チェックが無く、権限制御は UI（`isOwnEvent`）にしか無い | 更新・削除に「本人 or admin」の 403 チェックを追加 |
| 2 | （ユーザー要件） | 修正方針に対する見解 | **admin は例外**として扱う |

採用した案: 共通ヘルパー `_require_event_owner_or_admin(target, claims)` に判定を集約し、更新・削除・日時移動の
3 エンドポイントに適用する（DRY）。採用しなかった案は「`/date/update` の既存チェックのみに揃える（admin 例外なし）」=
ユーザー要件に反するため不採用。

---

## 2. 変更サマリ（差分）

変更ファイルは 3 件（`app/routers/timetable.py` +19/-5、`tests/conftest.py` +6、`tests/test_timetable.py` +133）。

| ファイル | 変更 |
|---|---|
| `app/routers/timetable.py` | 共通ヘルパー `_require_event_owner_or_admin` を追加し、`update_event_item` / `remove_event_item` / `update_event_dates` の 3 箇所に適用 |
| `tests/conftest.py` | 非 admin の登録ユーザー `staff 1002`（`StaffLogin` admin=False + `User`）を seed |
| `tests/test_timetable.py` | 新規 8 テストと補助 `_add_event_staff` を追加 |

### 2.1 共通ヘルパー（`app/routers/timetable.py:193-207`）

```python
def _require_event_owner_or_admin(target: "EventORM", claims: dict) -> None:
    """イベントの更新・削除は作成者本人または admin のみ許可する (Issue #20)。

    claims は require_token 由来で、user_id / admin キーが常に存在する。
    """
    if target.staff_id == claims.get("user_id"):
        return
    if claims.get("admin"):
        return
    raise HTTPException(
        status_code=403,
        detail="not allowed to modify other member's event",
    )
```

- `target.staff_id` と `claims["user_id"]` の一致 → 本人。`claims["admin"]` → 例外。どちらでもなければ 403。
- エラー文言は `/date/update` の旧文言「not allowed to update other member's event: {id}」から
  「not allowed to modify other member's event」に統一（文言はテストで固定していないため安全）。

### 2.2 3 エンドポイントへの適用（`app/routers/timetable.py`）

| エンドポイント | 行 | 変更 |
|---|---|---|
| `POST /event/update/{event_id}` | 218 | 404 チェック直後に `_require_event_owner_or_admin(target, claims)` を呼び出し追加 |
| `POST /date/update` | 251 | 従来の `if target.staff_id != claims.get("user_id"): raise 403` をヘルパー呼び出しに置換（admin 例外を追加） |
| `DELETE /event/remove/{event_id}` | 268 | 404 チェック直後にヘルパー呼び出しを追加 |

- **404 優先は維持**: 存在しないイベントは先に 404→ 権限判定（403）は存在確認の後。判定順は変えない。

---

## 3. 権限契約の変更

| エンドポイント | 変更前 | 変更後 |
|---|---|---|
| `POST /event/update/{id}` | `require_token` のみ（誰でも更新可） | **本人 or admin** のみ。それ以外は 403 |
| `DELETE /event/remove/{id}` | `require_token` のみ（誰でも削除可） | **本人 or admin** のみ。それ以外は 403（イベントは残存） |
| `POST /date/update` | 本人のみ（admin でも他メンバー不可） | **本人 or admin**。非本人で非 admin は 403 |

- **admin は例外**: 個別ユーザーのイベント更新・削除は本人のみの操作であるべきで、admin は全イベントに操作可能（ユーザー要件）。
- 存在しないイベント ID は従来どおり **404**。

---

## 4. テスト変更（`tests/test_timetable.py`）

| テスト | 内容 |
|---|---|
| `_add_event_staff`（補助） | admin トークンで任意 staff_id のイベントを作成し id を返す（「他人所有イベント」の用意） |
| `test_event_update_other_members_event_forbidden`（新規） | 他人の event 1 を非 admin 1002 が update → 403 |
| `test_event_update_owner_non_admin_allowed`（新規） | 非 admin でも本人の event は update → 200 / 反映 |
| `test_event_update_admin_can_modify_others`（新規） | admin が他人の event を update → 200 |
| `test_event_remove_other_members_event_forbidden`（新規） | 他人の event 1 を非 admin 1002 が delete → 403 + 残存を確認 |
| `test_event_remove_owner_non_admin_allowed`（新規） | 非 admin 本人の event は delete → 200 |
| `test_event_remove_admin_can_remove_others`（新規） | admin が他人の event を delete → 200 |
| `test_date_update_other_members_event_forbidden`（新規） | 他人の event を非 admin が date/update → 403 |
| `test_date_update_admin_can_move_others_event`（新規） | admin が他人の event を date/update → 200 |

> 補足: 判定に使う更新フィールドは `EventUpdate` に存在する `summary` を利用（`title` は `EventUpdate` に無いため使わない）。
> 非 admin の「他人」は `require_token` が `staff_id` を `StaffLogin` に照合するため、未登録 ID（例 9999）では 401 になってしまう。
> そのため `tests/conftest.py` に非 admin の登録ユーザー `staff 1002` を seed した（既存の event-1-count テストへ影響が出ないよう、イベントは追加せずユーザーのみ）。

---

## 5. 影響範囲・非対象

- **フロントエンド**（別リポジトリ `time-table-to-line`）: **実行時影響なし**。UI は既に `isOwnEvent` で管理済みのため、backend 側で保険を掛けた形。変更不要。
- **互換性**: 既存の本人・admin 操作は全て許可のまま。権限の無い不正アクセスのみが 403 になる。
- **DB スキーマ**: 変更なし（マイグレーション不要）。
- **既存契約への影響**: `/event/all` `/event/user` `/group/all`（`to_dict()` ベース）は不変。`/milestone/*/events` の公開キー契約も不変。
- **パフォーマンス**: 追加クエリなし。既存の 1 回の SELECT の結果に対して claims を比較するだけ。

---

## 6. 検証

| コマンド | 結果 |
|---|---|
| `python -m pytest -q`（ベースライン・変更前） | 79 passed |
| `python -m pytest tests/test_timetable.py::test_event_update_other_members_event_forbidden -q`（RED） | 1 failed（未チェックのため 200 が返る） |
| `python -m pytest tests/test_timetable.py -q`（Task1-5 完了後） | 26 passed |
| `python -m pytest -q`（全体・Task6） | **87 passed** |

検証観点:
- 更新・削除・日時移動の 3 端末で「本人 or admin」以外は 403
- 削除拒否時にイベントが残存すること（`1 in remaining`）
- 存在しないイベント ID は 404 のまま
- 共通ヘルパーが 3 箇所に集約されていること（`grep -n _require_event_owner_or_admin app/routers/timetable.py` → def 193 + 呼び出し 218 / 251 / 268）

---

## 7. 未決事項

- なし（admin 例外はユーザー要件で確定）。
- （参考）`tests/__pycache__/conftest.cpython-313-pytest-9.1.1.pyc` は git 管理下の tracked バイナリで、
  テスト実行のたびに `M` に変わる（本 Issue とは無関係・由来）。コミット対象から外すのが推奨。