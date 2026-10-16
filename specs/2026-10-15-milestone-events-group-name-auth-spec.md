# マイルストーン所属イベント取得 API 改訂仕様 — 変更履歴（Issue #40 / PR #15）

> 対象差分: `origin/main` (05a9acb) → `feature/milestone-events/40` (PR #15)
> **現行契約の正本は `2026-10-13-milestone-event-retrieval-spec.md` です。** 本ファイルは PR #15 で発生した**変更内容（差分）の記録**であり、正本の代替ではない。エンドポイント・レスポンス・権限マトリクス・エラー境界の現在の定義は正本を参照してください。
> 関連: 正本 `specs/2026-10-13-...`, `.hermes/rules/milestones.md`, フロント側仕様 `time-table-to-line/specs/2026-10-15-spec.md`

---

## 1. 変更の背景・動機

`open` / `waiting` 状態のマイルストーンに所属するイベント一覧を、**グループメンバー（非 admin を含む）が閲覧できる**ようにする。

変更前は open/waiting 用 `GET /milestone/{milestone_id}/events` が admin gate（非 admin は 403）で守られていたが、マイルストーンはグループ横断で共有される概念であり、Timeline 画面の「…」ボタンは全ユーザーに表示される。そのため所属イベント一覧の参照まで admin に限定すると UI と権限が噛み合わない。

| # | 動機 | 根拠 |
|---|---|---|
| 1 | 「…」ボタンが全ユーザーに表示され、開くと所属イベント一覧を表示する必要がある | 旧契約の `403 Forbidden`（admin gate）では非 admin で機能が破綻する |
| 2 | `group_id → group_name` はフロントで解決できない | `/group-names` はグループ“名のみ”を返し ID と対応しない。`/group/users` にもグループ名が無い → バックエンドに委譲 |

---

## 2. 変更サマリ（差分）

変更ファイルは 3 件（`+41 / -17`）。エンドポイント、レスポンス、権限マトリクス、エラー境界の**現行定義は正本 `2026-10-13-...` を参照**（本ファイルには記載しない）。

| ファイル | 変更 |
|---|---|
| `app/routers/timetable.py` | `_get_milestone_events` に `group_name` 付与を追加。`GET /milestone/{milestone_id}/events` の admin gate を撤去 |
| `specs/2026-10-13-milestone-event-retrieval-spec.md`（正本） | 上記に合わせて権限・レスポンス仕様を改訂 |
| `tests/test_milestone.py` | 権限緩和・`group_name`・403/404 分化に追随 |

### 2.1 `group_name` の付与（`app/routers/timetable.py:308-315`）

```python
events = db.query(EventORM).filter(EventORM.milestone_id == milestone_id).all()
result = []
for ev in events:
    d = ev.to_dict()
    # Issue #40: group_id -> group_name はフロントで解決不可のため、ここで Team から付与する。
    team = db.get(Team, d["group"])
    d["group_name"] = team.SHORTNAME if team else None
    result.append(d)
return result
```

- `group_name` の値は `M_TEAM.SHORTNAME`（モデル `Team.SHORTNAME`）。
- `Team` が未登録（`db.get(Team, group_id)` が `None`）の場合は `null`。
- 付与場所は共通ヘルパ `_get_milestone_events` のため、open/waiting 用と closed 用の**両 API に適用**される。
- イベント取得クエリ・グループ絞り込みの挙動は不変（全グループ横断のまま）。

### 2.2 閲覧権限の緩和（`app/routers/timetable.py:318-328`）

`GET /milestone/{milestone_id}/events` から

```python
if not claims.get("admin"):
    raise HTTPException(status_code=403, detail="admin only")
```

を撤去。`require_token` のみを依存に残す。**現行の権限マトリクス・403/404 の分化は正本 `2026-10-13-...` を参照。**

`GET /milestone/closed/{milestone_id}/events` の admin gate（`timetable.py:337-338`）は**変更なし**（変更前から admin 限定）。

---

## 3. テスト変更（`tests/test_milestone.py`）

| テスト | 変更 |
|---|---|
| `test_milestone_events_forbidden_for_non_admin` → `test_milestone_events_allowed_for_non_admin` | 非 admin の期待値を `403` → `200` に変更。所属イベントを 1 件作成し、返却 ID を検証 |
| `test_milestone_events_returns_events_across_groups` | `group_name` の検証を追加（conftest の `Team(3)/Team(4)` → `SHORT_A` / `SHORT_B`） |
| `test_non_admin_missing_milestone_returns_403` → `test_non_admin_missing_milestone_returns_404_vs_403` | 非 admin + 欠番で、open/waiting 用は `404` / closed 用は `403` の分化を 1 テストで検証 |
| `test_milestone_events_response_keys_and_format` | キー集合を 10 → 11 に更新（`group_name` 追加）し、値 `SHORT_A` を検証 |

---

## 4. 影響範囲・非対象

- **フロントエンド**（`gensukeSpp/time-table-to-line` PR `feature/events-from-milestone/39-`）: 非 admin でも「…」から一覧表示可能。`group_name` を表示に利用。バックエンドのみの改訂では UI 変更は不要。
- **DB スキーマ変更なし**: `group_name` は応答時に `M_TEAM` から都度解決（マイグレーション不要）。レスポンスのキー構成は正本を参照。
- **既存契約への影響なし**: closed 用 API、`/milestone/add|update|remove|all`、通常のイベント CRUD、自動 close（Task-11）は不変。
- **N+1 の注意**: `group_name` 付与はイベント件数ぶん `db.get(Team, ...)` を呼ぶ。同一グループのイベントが多い場合は Team を事前にまとめ引きする最適化余地がある（現状の要件規模では未対応）。
- **残件**: `.hermes/rules/milestones.md` の Permission model / API endpoints は依然「`GET /milestone/{id}/events` は admin のみ」と記載。正本への反映に合わせて更新が必要。

---

## 5. 検証

- `pytest` 全件パス（PR #15 記載: 72 passed / `tests/test_milestone.py` 含む）。
- 検証観点: 非 admin + open/waiting で 200、レスポンス 11 キー、`group_name` = `SHORTNAME`、非 admin + 欠番で open/waiting = 404 / closed = 403、`group_name` が `null` になる Team 未登録ケース。