---
created: 2026-10-23T15:30:00+09:00
updated: 2026-10-23T15:30:00+09:00
---

# Issue #22 — `/event/add` の staff_id を認証ユーザーと照合する

> 対象差分: ブランチ `feature/event-add-staff-check/22` の 2 コミット
> （`test: ... (RED)` 9edad96 / `fix #22: ...` 1c1e582。`origin/main` 起点）
> 本ファイルは Issue #22 で発生した**変更内容（差分）の記録**であり、機能ごとの現行契約の正本ではない。
> 権限モデル・API 契約の正は `.hermes/rules/milestones.md`（Permission model / API endpoints）を参照。
> 変更の入力: PR #21 レビュー（`.github/reports/pr-21-review.md`）指摘事項 1 より起票された Issue #22

---

## 1. 変更の背景・動機

PR #21 で Issue #20（更新・削除・日時移動の所有者チェック）を実装した際、**作成時は body の `staff_id` を
claims と照合していない**残欠陥が指摘された。認証済みの任意ユーザーが `staff_id=他人` でイベントを作成できる
と、作成されたイベントは他人名義になり、本人の `/event/user` 一覧に偽イベントが混入するほか、所有者ベースの
更新・削除チェック（「作成者 = staff_id」前提）と整合しなくなる（作成者は操作できず名義人が操作可能になる）。

| # | 指摘 | 内容 | 対応 |
|---|---|---|---|
| 1 | [Medium] 指摘 1 | `append_event_item`（170 行付近）が `body.staff_id` を無検証で採用。認証済みユーザーが他人名義のイベントを作成できる | 非 admin は `body.staff_id != claims["user_id"]` なら 403。admin は他人名義作成を許可 |

採用した案: 作成時専用ヘルパー `_require_event_create_owner_or_admin(staff_id, claims)` を新設し、
`append_event_item` の冒頭（`db.add` より前）で呼ぶ。採用しなかった案は「既存の更新・削除用
`_require_event_owner_or_admin` に統合」= 引数が event オブジェクト基準と body の素の int 基準で型が異なり、
無理に統合すると呼び出し側が不自然になるため不採用（可読性優先）。

---

## 2. 変更サマリ（差分）

変更ファイルは 2 件（`app/routers/timetable.py` +19、`tests/test_timetable.py` +59、計 +78）。

| ファイル | 変更 |
|---|---|
| `app/routers/timetable.py` | 作成時専用ヘルパー `_require_event_create_owner_or_admin` を追加し、`append_event_item` 冒頭で呼び出し |
| `tests/test_timetable.py` | Issue #22 セクション（新規 4 テスト + 補助 `_create_event_body`）を追加 |

### 2.1 作成時チェック（`app/routers/timetable.py:170-188`）

```python
def _require_event_create_owner_or_admin(staff_id: int, claims: dict) -> None:
    """/event/add の staff_id を認証ユーザーと照合する (Issue #22)。

    非 admin は本人の staff_id のみ許可。admin は他人名義の作成を許可する。
    更新・削除用の _require_event_owner_or_admin は event オブジェクト基準なので、
    作成時は body の素の staff_id を受ける本関数を使う。
    claims は require_token 由来で、user_id / admin キーが常に存在する。
    """
    if staff_id == claims.get("user_id"):
        return
    if claims.get("admin"):
        return
    raise HTTPException(
        status_code=403,
        detail="not allowed to create event for other member",
    )
```

### 2.2 `append_event_item` への適用（`app/routers/timetable.py:191-194`）

`event = EventORM(...)` の**前**（`db.add` より前）に呼び出し 1 行を追加。

```python
@router.post("/event/add", status_code=201)
def append_event_item(
    body: EventCreate,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    _require_event_create_owner_or_admin(body.staff_id, claims)
    event = EventORM(
```

- 判定を `db.add` の前に行うため、403 時に DB へは何も書かれない（受け入れ条件 2: イベントは作成されない）。
- `HTTPException` は既存 import（更新・削除用ヘルパーが使用）をそのまま利用。新規 import なし。
- `app/schemas.py`（`EventCreate.staff_id: int` 必須）・`app/models.py` は変更なし。

---

## 3. 権限契約の変更

| エンドポイント | 変更前 | 変更後 |
|---|---|---|
| `POST /event/add` | `require_token` のみ。body の `staff_id` を無検証で採用（他人名義作成できる） | **非 admin は `staff_id == claims["user_id"]` のみ許可**（不一致は 403・DB 未書き込み）。**admin は他人名義の作成を許可**。本人・admin の従来作成挙動は不変 |

- 判定順: 401（`require_token` / 未認証・未登録ユーザー）→ 422（Pydantic / `staff_id` 非 int）→ 403（本チェック）。
- 非 admin が存在しない `staff_id`（例 9999）を指定した場合も claims との不一致として 403（ユーザー存在検証は今回スコープ外）。
- admin が存在しない `staff_id` で作成した場合は従来どおり 201（既存挙動を維持・スコープ外）。
- 403 の detail は「not allowed to create event for other member」。更新・削除用の
  「not allowed to modify other member's event」とは意図的に別文言（テスト・フロントとも文言に依存せず）。

---

## 4. テスト変更（`tests/test_timetable.py` 末尾の Issue #22 セクション）

| テスト | 内容 | 受入条件 |
|---|---|---|
| `_create_event_body`（補助） | 有効な body（staff_id 可変）を返す。既存 `_add_event_staff` とは違い、どのトークンでも使える | — |
| `test_event_add_self_non_admin_allowed`（新規） | 非 admin 1002 が自分の staff_id=1002 で作成 → 201 + staff_id 反映 | 受入 1 |
| `test_event_add_other_member_forbidden_for_non_admin`（新規） | 非 admin 1002 が他人 staff_id=1001 → 403 + `/event/all` に混入しない（件数・名義とも不変） | 受入 2 |
| `test_event_add_admin_can_create_for_others`（新規） | admin 1001 が他人 staff_id=1002 → 201 | 受入 3 |
| `test_event_add_nonexistent_staff_forbidden_for_non_admin`（新規） | 非 admin 1002 が存在しない staff_id=9999 → 403 | エッジ（受入 2 の拡張） |

> 補助: issue-20 セクションの `_add_event_staff`（admin が任意 staff_id で 201 を期待）は**そのまま通る**
> （admin 例外を許可のままにしたため）。conftest の seed（staff 1001 admin / staff 1002 非 admin、イベント 1 件
> staff_id=1001）を再利用。トークンは `tokens.create_access_token(user_id, group_id, admin)` の Bearer 直接生成。

---

## 5. 影響範囲・非対象

- **フロントエンド**（別リポジトリ `time-table-to-line`）: **実行時影響なし**。UI は自分の staff_id を送る想定で
  （`isOwnEvent` 管理済み・issue-20 レビュー参照）、403 は API 直叩きのみで発生。変更不要。
- **互換性**: 本人・admin の従来作成は全て許可のまま。権限の無い他人名義作成のみが 403 になる。
- **DB スキーマ**: 変更なし（マイグレーション不要）。追加クエリなし。
- **既存エンドポイント**: 更新・削除・日時移動・マイルストーン系は不変（`_require_event_owner_or_admin` や
  `/milestone/*` の契約を触っていない）。
- **非対象**: `EventCreate` / claims 構造 / 認証契約（Bearer 優先・Cookie フォールバック）の変更なし。
  `tests/__pycache__/*.pyc` の tracked 変化は従来どおりコミット対象外。

---

## 6. 検証

| コマンド | 結果 |
|---|---|
| `uv run pytest -q`（ベースライン・変更前） | 87 passed |
| `uv run pytest tests/test_timetable.py -k "event_add" -v`（RED・テストのみ） | **2 failed**（他人 1001 / 不明 9999 が 403 期待で 201 を受ける） |
| `uv run pytest -q`（RED 時・全体） | 2 failed, 89 passed（新規 2 件のみ失敗、他は無影響） |
| `uv run pytest tests/test_timetable.py -k "event_add" -v`（GREEN） | 5 passed（既存 `test_event_add` 含む） |
| `uv run pytest tests/test_timetable.py -v` | 32 passed |
| `uv run pytest tests/test_milestone.py -q` | 51 passed（milestone 経由の `/event/add` = admin は無影響） |
| `uv run pytest -q`（全体） | **91 passed**（87 + 新規 4） |
| smoke: `uvicorn app.main:app` 起動 → `GET /health` | 200 `{"status":"ok"}` |

検証観点:
- 非 admin の本人作成 201 / 他人名義 403（一覧不変）/ 不明 ID 403 / admin の他人名義 201
- 403 時に `/event/all` へイベントが混入しないこと（`len(after) == len(before) == 1` + 名義確認）
- issue-20 の所有者チェック 7 件・milestone テスト 51 件が無傷

---

## 7. 未決事項

- なし（admin 例外は issue 方針どおり確定）。
- （参考）admin が存在しない `staff_id` でイベントを作成できる挙動（201）は従来どおり維持。ユーザー単位の
  存在検証が必要になった場合は別 Issue で扱う。
