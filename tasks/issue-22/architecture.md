# Issue-22 設計 — `/event/add` の staff_id 所有者照合

## 1. 対象フロー（現状）

```
client → POST /event/add {staff_id, group, start_time, end_time, title, ...}
  → require_token: Bearer/Cookie から claims {user_id, group_id, admin} を検証（401 あり）
  → EventCreate の Pydantic バリデーション（staff_id が int でない → 422）
  → append_event_item:
      EventORM(staff_id=body.staff_id, ...)  ← ★ claims と未照合（問題箇所）
      db.add → commit → refresh → return to_dict() 201
```

## 2. 変更後のフロー

```
  → append_event_item:
      _require_event_create_owner_or_admin(body.staff_id, claims)   ← 追加（db.add より前）
          · staff_id == claims["user_id"]        → 許可（本人）
          · claims["admin"] == True              → 許可（admin 例外）
          · else                                 → raise HTTPException(403)（DB 未書き込み）
      EventORM(staff_id=body.staff_id, ...)（従来どおり）
      db.add → commit → refresh → return to_dict() 201
```

判定は **`db.add` より前**に行うため、403 時にイベントは一切作成されない（受入条件 2）。

## 3. 実装コード（コピペ完全形）

`app/routers/timetable.py` の `append_event_item`（171 行目）の直前に追加:

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

`append_event_item`（170-190 行目）の冒頭に呼び出し 1 行を追加:

```python
@router.post("/event/add", status_code=201)
def append_event_item(
    body: EventCreate,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    _require_event_create_owner_or_admin(body.staff_id, claims)
    event = EventORM(
        staff_id=body.staff_id,
        ...
```

※ `HTTPException` は `app/routers/timetable.py` 冒頭で import 済み（既存 `_require_event_owner_or_admin` が使用）。
※ 新規 import は不要。

## 4. 設計判断の根拠

| 論点 | 判断 | 理由 |
|---|---|---|
| ヘルパーの分離 | 既存 `_require_event_owner_or_admin` とは別関数 | 既存は `target.staff_id`（event オブジェクト）、新規は `body.staff_id`（int）。引数型が違い、無理に統合すると呼び出し側が不自然になる |
| 呼び出し位置 | `append_event_item` 冒頭、`db.add` の前 | 403 時に DB 書き込みゼロを保証（受入条件 2）。`require_token` の後なので claims は検証済み |
| 403 の文言 | `"not allowed to create event for other member"` | 更新/削除用の `"not allowed to modify other member's event"` と意味を分ける。既存テストは文言固定なし、フロントもステータスで判定する想定のため安全 |
| 404 は使わない | 403 のみ | staff_id の「存在しないユーザー」判定は今回対象外。不一致は「他人名義」として 403 で返す（ユーザー ID の存在隠蔽も不要） |
| admin 判定 | `claims.get("admin")` のみ | issue の方針「admin は他人名義のイベント作成を許可」どおり。既存 `_add_event_staff`（issue-20 のテストヘルパー）が任意 staff_id で 201 を期待しており、これが壊れない条件と一致 |
| 認証エラー順 | 401（require_token）→ 422（Pydantic）→ 403（本チェック） | 既存フローの前に割り込ませない。無トークンの 401 は従来どおり |

## 5. エッジケースと期待挙動

| ケース | claims | body.staff_id | 期待 |
|---|---|---|---|
| 本人かつ非 admin | user_id=1002, admin=False | 1002 | 201（受入 1） |
| 他人名義・非 admin | user_id=1002, admin=False | 1001 | 403・イベント不作成（受入 2） |
| 他人名義・admin | user_id=1001, admin=True | 1002 | 201（受入 3） |
| 存在しない ID・非 admin | user_id=1002, admin=False | 9999 | 403（不一致として自然に拒否） |
| 存在しない ID・admin | user_id=1001, admin=True | 9999 | 201（スコープ外・従来挙動維持） |
| 本人かつ admin | user_id=1001, admin=True | 1001 | 201（既存 `test_event_add` が回帰確認） |
| 無トークン | — | — | 401（変更なし・`require_token`） |
| staff_id 非 int | — | "abc" | 422（Pydantic・変更なし） |

## 6. 変更ファイル一覧

| 種別 | パス | 内容 |
|---|---|---|
| Modify | `app/routers/timetable.py:170-190` | ヘルパー `_require_event_create_owner_or_admin` 追加 + `append_event_item` 冒頭に呼び出し 1 行 |
| Modify | `tests/test_timetable.py`（末尾） | Issue #22 セクション追加（テスト 4 件） |
| New（任意・実装後） | `specs/<date>-event-add-staff-owner-spec.md` | 差分配録（spec-change-records スキルの流儀に従う） |

※ `app/schemas.py` / `app/tokens.py` / `app/models.py` は変更なし。
※ DB スキーマ・マイグレーションなし。

## 7. 既存テストへの影響

- `tests/test_timetable.py:73 test_event_add`: 1001（admin）が staff_id=1001 → 許可 201。**通る**
- `tests/test_timetable.py:233 _add_event_staff`: admin が任意 staff_id → 許可 201。**通る**（issue-20 の 7 テストが依存）
- `tests/test_milestone.py:31-42 _add_event`: admin（1001）が staff_id=1001 → 許可 201。**通る**
- 非 admin で既存の `/event/add` を呼ぶテストは存在しない → **既存テストの挙動変化なし**

## 8. リスク / トレードオフ

- **フロントへの影響**: UI は自分の staff_id を送る想定（`isOwnEvent` 管理済み・issue-20 レビュー参照）。
  非本人操作の UI 経路が無いことが確認済みなら実行時の挙動変化なし。403 は API 直叩きのみで発生。
- **admin の他人名義作成が残る**: 要件どおり許可するため、admin は従来どおり任意名義で作成できる
  （意図された特権。閉じ処理 `/milestone/*` も admin 専用で同様の設計）。
- **スコープ依存**: 今回のチェックは Issue #20 の「所有者 = 作成者」前提を補強する。両 Issue のテストが
  揃うことで権限モデルが一貫する。
