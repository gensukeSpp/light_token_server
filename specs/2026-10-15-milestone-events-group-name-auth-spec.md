# マイルストーン所属イベント取得 API 改訂仕様（Issue #40 / PR #15）

> 対象差分: `origin/main` (05a9acb) → `feature/milestone-events/40` (PR #15)
> 関連: `specs/2026-10-13-milestone-event-retrieval-spec.md`（本改訂で更新）,
> `.hermes/rules/milestones.md`, フロント側仕様 `time-table-to-line/specs/2026-10-15-spec.md`

---

## 1. 目的

`open` / `waiting` 状態のマイルストーンに所属するイベント一覧を、**グループメンバー（非 admin を含む）が閲覧できる**ようにする。

マイルストーンはグループ横断で共有される概念であり、Timeline 画面の「…」ボタンは全ユーザーに表示される。そのため所属イベント一覧の参照まで admin に限定すると UI と権限が噛み合わない。本改訂は閲覧権限を `require_token`（認証済みなら誰でも）まで緩和し、あわせてフロントで解決できない **グループ名（`group_name`）をレスポンスに付与**する。

### 変更の動機

| # | 動機 | 根拠 |
|---|---|---|
| 1 | 「…」ボタンが全ユーザーに表示され、開くと所属イベント一覧を表示する必要がある | 旧契約の `403 Forbidden`（admin gate）では非 admin で機能が破綻する |
| 2 | `group_id → group_name` はフロントで解決できない | `/group-names` はグループ“名のみ”を返し ID と対応しない。`/group/users` にもグループ名が無い → バックエンドに委譲 |

---

## 2. 変更サマリ（差分）

変更ファイルは 3 件（`+41 / -17`）。

| ファイル | 変更 |
|---|---|
| `app/routers/timetable.py` | `_get_milestone_events` に `group_name` 付与を追加。`GET /milestone/{milestone_id}/events` の admin gate を撤去 |
| `specs/2026-10-13-milestone-event-retrieval-spec.md` | 上記に合わせて権限・レスポンス仕様を改訂 |
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

を撤去。`require_token` のみを依存に残す。

`GET /milestone/closed/{milestone_id}/events` の admin gate（`timetable.py:337-338`）は**変更なし**。

---

## 3. API 契約

### 3.1 open / waiting マイルストーンのイベント取得

`GET /milestone/{milestone_id}/events`

| 項目 | 内容 |
|---|---|
| 認証 | 有効なアクセストークン必須（`Authorization: Bearer {token}`）。**admin 判定は行わない** |
| 対象 | `status` が `open` または `waiting` のマイルストーン |
| 取得範囲 | 指定マイルストーンに `milestone_id` が一致する全イベント。全グループ横断（トークンの `group_id` による絞り込みはしない） |
| 成功 | `200 OK` + イベントオブジェクトの JSON 配列（§4）。該当なしは `[]` |
| 状態不一致 / 欠番 | `404 Not Found`（存在しない ID、`closed` など対象外状態の ID） |
| 順序 | 保証しない |

### 3.2 closed マイルストーンのイベント取得（変更なし）

`GET /milestone/closed/{milestone_id}/events`

| 項目 | 内容 |
|---|---|
| 認証 | 有効なトークン必須 + **`admin` claim が真**（非 admin は `403 Forbidden`） |
| 対象 | `status` が `closed` のマイルストーン（管理者 close・waiting からの自動 close の両方を含む） |
| 成功 | `200 OK` + §4 形式の配列 |
| 状態不一致 / 欠番 | `404 Not Found` |

---

## 4. レスポンス仕様（変更点は `group_name` の追加）

各要素は既存イベント取得 API（`EventORM.to_dict()`）の形式に `group_name` を加えた **11 キー**（旧 10 キー）。日時形式は `YYYY-MM-DDTHH:mm:ss.000Z`。

| キー | 内容 |
|---|---|
| `id` | イベント ID |
| `staff_id` | イベント作成者 ID |
| `group` | 所属グループ ID（`T_TIMELINE_EVENT.group_id` / `M_TEAM.CODE`） |
| `group_name` | **追加（Issue #40）**: 所属グループ名 = `M_TEAM.SHORTNAME`。Team 未登録なら `null` |
| `start` | 開始日時 |
| `end` | 終了日時 |
| `title` | イベントタイトル |
| `summary` | 概要（未設定は `null`） |
| `progress` | 進捗（未設定は `null`） |
| `milestone_id` | 所属マイルストーン ID |
| `completed` | 完了状態 |

---

## 5. 権限マトリクス

| エンドポイント | 非 admin | admin |
|---|---|---|
| `GET /milestone/{milestone_id}/events`（open/waiting） | **200（本改訂で許可）** | 200 |
| `GET /milestone/closed/{milestone_id}/events` | 403 | 200 |
| `POST /milestone/add` | 403 | 201 |
| `POST /milestone/update/{id}` | 403 | 200 |
| `DELETE /milestone/remove/{id}` | 403 | 200 |
| `GET /milestone/all` | 200 | 200 |

本改訂の対象は open/waiting 用の参照 1 本のみで、**マイルストーンの作成・更新・close・削除は admin 限定のまま**。

---

## 6. エラーと境界（403 / 404 の分化）

| 状況 | open/waiting 用 | closed 用 |
|---|---|---|
| トークン無効・期限切れ | 401（`require_token` の契約に従う） | 401 |
| 認証済み・非 admin | 200（許可） | 403 |
| 認証済み・非 admin・存在しない ID | **404**（admin gate が無いため存在判定が先） | **403**（admin gate を先に判定） |
| 認証済み・admin・存在しない ID | 404 | 404 |
| 対象状態と異なる ID | 404 | 404 |

- `404` はマイルストーン本体の取得（`status.in_` フィルタ）で判定し、イベント配列は返さない。
- ページネーション・絞り込み・更新・削除は本 API の対象外。

---

## 7. テスト変更（`tests/test_milestone.py`）

| テスト | 変更 |
|---|---|
| `test_milestone_events_forbidden_for_non_admin` → `test_milestone_events_allowed_for_non_admin` | 非 admin の期待値を `403` → `200` に変更。所属イベントを 1 件作成し、返却 ID を検証 |
| `test_milestone_events_returns_events_across_groups` | `group_name` の検証を追加（conftest の `Team(3)/Team(4)` → `SHORT_A` / `SHORT_B`） |
| `test_non_admin_missing_milestone_returns_403` → `test_non_admin_missing_milestone_returns_404_vs_403` | 非 admin + 欠番で、open/waiting 用は `404` / closed 用は `403` の分化を 1 テストで検証 |
| `test_milestone_events_response_keys_and_format` | キー集合を 10 → 11 に更新（`group_name` 追加）し、値 `SHORT_A` を検証 |

---

## 8. 影響範囲・非対象

- **フロントエンド**（`gensukeSpp/time-table-to-line` PR `feature/events-from-milestone/39-`）: 非 admin でも「…」から一覧表示可能。`group_name` を表示に利用。バックエンドのみの改訂では UI 変更は不要。
- **DB スキーマ変更なし**: `group_name` は応答時に `M_TEAM` から都度解決（マイグレーション不要）。
- **既存契約への影響なし**: closed 用 API、`/milestone/add|update|remove|all`、通常のイベント CRUD、自動 close（Task-11）は不変。
- **N+1 の注意**: `group_name` 付与はイベント件数ぶん `db.get(Team, ...)` を呼ぶ。同一グループのイベントが多い場合は Team を事前にまとめ引きする最適化余地がある（現状の要件規模では未対応）。
- **残件**: `.hermes/rules/milestones.md` の Permission model / API endpoints は依然「`GET /milestone/{id}/events` は admin のみ」と記載。本改訂を反映する更新が未実施。

---

## 9. 検証

- `pytest` 全件パス（PR #15 記載: 72 passed / `tests/test_milestone.py` 含む）。
- 検証観点: 非 admin + open/waiting で 200、レスポンス 11 キー、`group_name` = `SHORTNAME`、非 admin + 欠番で open/waiting = 404 / closed = 403、`group_name` が `null` になる Team 未登録ケース。
