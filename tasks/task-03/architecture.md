# Task-03 アーキテクチャ詳細

## 1. モジュール構成と import の流れ

既存の CRUD と同じく、`app/routers/timetable.py` に `/milestone/*` を追加する。**新規ルーターは作らない** — `main.py` は既に `from .routers import timetable` + `app.include_router(timetable.router)` をしているため、既存ルーターにハンドラを足すだけで配線される。

```
app/database_base.py  (engine / Base / get_db)
   ^
app/models.py         (MilestoneORM, EventORM.milestone_id/completed)  ← Task 1 済
   ^
app/schemas.py        (MilestoneCreate / MilestoneUpdate / Event 拡張) ← Task 2 済
app/tokens.py         (require_token / get_token_claims / claims)
   ^
app/routers/timetable.py  (既存 /event/* に /milestone/* を追加)       ← 本タスク
   ^
app/main.py           (既存 include_router。変更不要)
```

認可は既存 `require_token`(Bearer 優先 -- httpOnly Cookie フォールバック)を流用し、claims から `user_id`(作成者)、`group_id`、`admin`(権限判定)を読む。

## 2. モデルの契約(前タスクで実装済み)

`app/models.py` の `MilestoneORM`:

| カラム | 型 | 備考 |
|---|---|---|
| id | Integer, PK | |
| staff_id | Integer, FK→M_LOGGININFO.STAFFID | 作成者ID(== claims.user_id) |
| title | String(100) | |
| description | String(256), nullable | |
| color | String(10) | カラーコード `#xxxxxx` |
| status | Boolean, default=True | True=open / False=closed |
| created_at | Date | 作成日(時刻不要) |
| guidline_end_date | Date, nullable | 達成目安日 |
| accomplished_date | Date, nullable | 達成日(入力=close) |

`EventORM` 追加分: `milestone_id`(FK→M_MILESTONE.id, nullable)、`completed`(Boolean, default=False)。

- `to_dict()` は既に `milestone_id` / `completed` を含む(Iso 形式は従来どおり `%Y-%m-%dT%H:%M:%S.000Z`)。
- `MilestoneORM.to_dict()` は date を `isoformat()` で返す。created_at は必ず入る(カラム NOT NULL)、guidline/accomplished は nullable。

## 3. スキーマ定義(前タスクで実装済み)

- `MilestoneCreate`: `title: str` / `description: str | None` / `guidline_end_date: date | None`。`staff_id` / `status` / `color` / `created_at` はサーバー側で設定する。
- `MilestoneUpdate`: `accomplished_date: date`。close 専用(再 open は不可)。
- `EventCreate`: 既存 + `milestone_id: int | None = None` / `completed: bool = False`(optional 追加)。
- `EventUpdate`: 既存 + `milestone_id: int | None = None` / `completed: bool | None = None`(optional 追加)。

## 4. 色の自動選択(本タスクのコアロジック)

requirement-03.md / AGENTS.md の 10 固定パターンをモジュール定数(`MILESTONE_COLORS`)で保持:

```python
MILESTONE_COLORS = [
    "#9c27b0", "#009688", "#795548", "#607d8b", "#e91e63",
    "#3f51b5", "#00bcd4", "#ff5722", "#8bc34a", "#ff9800",
]
```

add 時に open 中のマイルストーンが使っている色を収集し、パレット先頭から `used` に無い色を選ぶ:

```python
def _next_color(db: Session) -> str:
    used = {
        m.color
        for m in db.query(MilestoneORM).filter(MilestoneORM.status.is_(True)).all()
    }
    for c in MILESTONE_COLORS:
        if c not in used:
            return c
    # 10 件全部使用中 → 1 番目から cyclic に戻す
    return MILESTONE_COLORS[0]
```

- open 中(閉じたものを含まず)だけが色を占有する。closed / 削除されたものは次の add で再利用可。
- 元図: 要件に「open されているマイルストーンとなるべく被らないように」。本実装は「open 中の既存と完全に被らない未使用色」を選ぶ。
- ⚠️ **将来 re-open 拡張との整合**: 再 open 可にする場合、「closed だが(表示期間中)まだ見えている」マイルストーンが再び open に戻る可能性があるため、色の再利用は**「open or 表示中のものでない色」**へ基準を変える必要が出る(今回の実装は「open 中のみ占有」のままでよい — 再 open 予定とは別項目として future 判断)。

## 5. エンドポイント仕様

`/milestone/*` は `app/routers/timetable.py` に既存 `/event/*` と同じ形で追記する。

### POST /milestone/add — 201

- 認可: `require_token` + `claims["admin"]` が True のときのみ(非 admin は 403)。
- 入力: `body: MilestoneCreate`
- サーバー側決定: `staff_id = claims["user_id"]`、`color = _next_color(db)`、`status = True`、`created_at = date.today()`。
- 応答: `status_code=201`、作成したマイルストーンの `to_dict()`。

```python
@router.post("/milestone/add", status_code=201)
def add_milestone(
    body: MilestoneCreate,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    if not claims.get("admin"):
        raise HTTPException(status_code=403, detail="admin only")
    ms = MilestoneORM(
        staff_id=claims["user_id"],
        title=body.title,
        description=body.description,
        color=_next_color(db),
        status=True,
        created_at=date.today(),
        guidline_end_date=body.guidline_end_date,
    )
    db.add(ms)
    db.commit()
    db.refresh(ms)
    return ms.to_dict()
```

### GET /milestone/all — 200
- 認証: `require_token` のみ(全ユーザー閲覧可、admin 不要)。
- open(status=True)のマイルストーンを返す。グループ横断共有のため `group_id` フィルタはしない(要件: 全てのグループで同じ表示)。

```python
@router.get("/milestone/all")
def get_open_milestones(
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    rows = db.query(MilestoneORM).filter(MilestoneORM.status.is_(True)).all()
    return [m.to_dict() for m in rows]
```

### POST /milestone/update/{id} — 200(close)
- 認証: `require_token` + admin(403)。
- 入力: `body: MilestoneUpdate`(accomplished_date)。
- 存在しない id は 404。
- **既に status=False(closed)なら 409**(再 open 不可)。→ 判断ポイント参照。
- close 処理:
  1. `target.status = False`、`target.accomplished_date = body.accomplished_date`
  2. 子イベント連動: `EventORM.milestone_id == id` の全行 `completed = True` を一括 UPDATE(`db.query(EventORM).filter(...).update({EventORM.completed: True})`)
  3. commit 後、`to_dict()` を返す

```python
@router.post("/milestone/update/{milestone_id}")
def close_milestone(
    milestone_id: int,
    body: MilestoneUpdate,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    if not claims.get("admin"):
        raise HTTPException(status_code=403, detail="admin only")
    target = db.query(MilestoneORM).filter(MilestoneORM.id == milestone_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="milestone not found")
    if target.status is False:
        raise HTTPException(status_code=409, detail="already closed")
    target.status = False
    target.accomplished_date = body.accomplished_date
    for ev in db.query(EventORM).filter(EventORM.milestone_id == milestone_id).all():
        ev.completed = True
    db.commit()
    db.refresh(target)
    return target.to_dict()
```

> **将来拡張のための注記(今回見送り・再 open 可予定):**
> 現行は「一度 closed したら再 open 不可」のため、close 済みへは 409 を返す(利用者確認済み 2026-08)。ただし将来、`requirement-03.md` 操作の流れ 4 の「何日か後に表記が消える」と組み合わせて、**表記している間は再 open できる**拡張を予定している。実装時に status 遷移の分岐(`if target.status is False: 409`)を**エンドポイント内の小さな遷移関数(`_apply_milestone_close` 等)に集約**し、将来 re-open 分岐を足す際にこの関数だけ改修すれば済む構造にしておく。この拡張では「closed だが表示中」の表現(accomplished_date からの経過日、または別フラグ)を future の判断で決める(今回のスキーマは増やさない)。

### DELETE /milestone/remove/{id} — 200 (soft close, 物理削除しない)
- 認証: `require_token` + admin(403)。
- 存在しない id は 404。
- 処理: **DB からは削除せず** `target.status = "closed"` に変更し、子イベント(`milestone_id` が一致する
  `T_TIMELINE_EVENT`)の `completed = True` に更新する(close と同じ連動)→ `{"closed": id}` を返す。
  旧仕様の「子イベント milestone_id を None にして物理削除」は廃止。

```python
@router.delete("/milestone/remove/{milestone_id}")
def remove_milestone(
    milestone_id: int,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    if not claims.get("admin"):
        raise HTTPException(status_code=403, detail="admin only")
    target = db.query(MilestoneORM).filter(MilestoneORM.id == milestone_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="milestone not found")
    target.status = MILESTONE_CLOSED
    for ev in db.query(EventORM).filter(EventORM.milestone_id == milestone_id).all():
        ev.completed = True
    db.commit()
    return {"closed": milestone_id}
```

### 既存 /event/* への milestone_id / completed 反映

`POST /event/add`:

```python
event = EventORM(
    staff_id=body.staff_id,
    group_id=body.group,
    start_time=convert_str_to_date(body.start_time),
    end_time=convert_str_to_date(body.end_time),
    title=body.title,
    summary=body.summary,
    progress=body.progress,
    milestone_id=body.milestone_id,
    completed=body.completed,
)
```

`POST /event/update/{event_id}`:

```python
if body.milestone_id is not None:
    target.milestone_id = body.milestone_id
if body.completed is not None:
    target.completed = body.completed
```

※ `EventCreate` / `EventUpdate` は既に default 付きの optional フィールドとして追加済みなので、スキーマは触らない。

## 6. 認可・権限モデル

- `admin=True` のユーザー全員が作成/close/削除可能(「そのグループの管理者」という限定的な表現を避けて、全 admin を対象とする — AGENTS.md 準拠)。
- 閲覧(`GET /milestone/all`)は require_token のみで、グループをまたいで全 open マイルストーンを返す。
- claims に `admin` が無い場合(旧トークン等)は falsy として 403。

## 7. セキュリティ

- 既存の `require_token` / `get_token_claims` は Bearer ヘッダー優先 + httpOnly Cookie フォールバックを維持(呼び出し側 time-table-to-line との契約を壊さない)。
- FastAPI 1.4.1 の制約に従う: リダイレクトは `raise HTTPException(303, headers={"Location": ...})` を使い、`raise RedirectResponse(...)` を使ってはならない(本タスクでは milestone 系には 303 は無いが、共通注意として)。
- DB は必ず `Depends(get_db)` 経由(絶対に `SessionLocal()` 直呼びしない)。

## 8. 依存追加(manifest)

- **追加必要なし**。マイルストーンは既存依存(FastAPI, SQLAlchemy, PyJWT, Pydantic, httpx)だけで実装できる。色の計算、日付、query はいずれも stdlib / 既存依存。
- `python-multipart` は不要(/milestone/* は JSON body)。

## 9. 実装時の注意(既存テストとの関係)

- `tests/test_timetable.py` の既存テストのうち 10 件(試行時に `test_timetable_auth_sets_http_only_cookies` 等)は**ブランチのベース状態から既に失敗**している(セッションクッキーまわりの既知問題で、マイルストーンとは無関係)。→ 本タスクのテストはこれらに**影響されないよう、独立した `tests/test_milestone.py` と `_login` + Bearer トークン手順で書く**。既存の `test_bearer_header_only_*` と同様に、`tokens.create_access_token(1001, 3, True)` で Bearer を直接作る方式が安全。
- `test_timetable` の失敗を修正するのは本タスクのスコープ外(別 Task)。