# マイルストーン機能 バックエンド実装計画

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** マイルストーン関連の DB モデル、Pydantic スキーマ、API エンドポイントをバックエンドに追加する

**Architecture:** 既存 CRUD パターン（models.py → schemas.py → routers/timetable.py）を踏襲。既存 `/event/add` スキーマに `milestone_id` optional 追加。DB マイグレーションはユーザー手動。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, httpx

---

## 重要制約

- **DB マイグレーションは実行しない。** 手動でユーザーが実行する。
- **frontend は実装しない。** バックエンド API のみ。
- **既存コードを壊さない。** 既存エンドポイントの振る舞いは変更しない。
- **TDD 方式。** 各タスクでまず failing test を書き、実装、pass 確認。
- **`get_db` のみ使用。** `SessionLocal()` は使わない。
- **Starlette 1.4.1 準拠。** `RedirectResponse` の raise 禁止。`HTTPException(303, ...)` を使う。
- `staff_id` FK は現時点で `M_LOGGININFO.STAFFID`。後で必要に応じて `M_STAFFINFO.STAFFID` に変更可能。

## マイルストーン決定事項（AGENTS.md 反映済み）

- テーブル名: `M_MILESTONE`（既存規則 `M_STAFFINFO` 合わせ）
- `created_at` 型: `Date()`（時刻不要）
- 権限: `admin=True` ユーザー全員が作成/クローズ/削除可能
- `completed`: マイルストーン close 時に属する全イベントを自動 `True`
- `completed=True` または `milestone_id` 未設定のイベントはデフォルト色 `#2196f3`
- カラー: 10 固定パターン、被り回避、10 件超えは cyclic
- 削除: `DELETE /milestone/remove/{id}` を追加（UI 削除ボタン用）

---

### Task 1: MilestoneORM モデルを追加

**Objective:** `app/models.py` に `M_MILESTONE` テーブルの ORM クラスと `EventORM` に `milestone_id`/`completed` フィールドを追加する。

**Files:**
- Modify: `app/models.py`

**Step 1: `M_MILESTONE` テーブルの列定義を追加**

`app/models.py` の末尾（EventORM の後）に以下のクラスを追加:

```python
class MilestoneORM(Base):
    __tablename__ = "M_MILESTONE"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("M_LOGGININFO.STAFFID"), nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(String(256), nullable=True)
    color = Column(String(10), nullable=False)
    status = Column(Boolean, default=True, nullable=False)
    created_at = Column(Date, nullable=False, default=datetime.today)
    guidline_end_date = Column(Date, nullable=True)
    accomplished_date = Column(Date, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "staff_id": self.staff_id,
            "title": self.title,
            "description": self.description,
            "color": self.color,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "guidline_end_date": self.guidline_end_date.isoformat() if self.guidline_end_date else None,
            "accomplished_date": self.accomplished_date.isoformat() if self.accomplished_date else None,
        }
```

**Step 2: EventORM に `milestone_id` と `completed` を追加**

既存 EventORM（app/models.py 92-117 行目）の末尾に 2 行追加:

```python
    milestone_id = Column(Integer, ForeignKey("M_MILESTONE.id"), nullable=True)
    completed = Column(Boolean, default=False, nullable=False)
```

`to_dict()` にも 2 行追加:

```python
            "milestone_id": self.milestone_id,
            "completed": self.completed,
```

**Step 3: 構文チェック**

```bash
cd /home/nabu_dvl/workspace/the-calendar-to-timeline/light_token_server
source .venv/bin/activate
python -c "from app.models import MilestoneORM, EventORM; print('OK')"
```

Expected: `OK` （インポートエラーなし）

**Step 4: Commit**

```bash
git add app/models.py
git commit -m "feat: add MilestoneORM model and milestone_id/completed to EventORM"
```

---

### Task 2: Pydantic スキーマを追加

**Objective:** `app/schemas.py` にマイルストーン関連のスキーマと、EventCreate に milestone_id を追加する。

**Files:**
- Modify: `app/schemas.py`

**Step 1: MilestoneCreate/Update/Response スキーマを追加**

`app/schemas.py` の末尾に追加:

```python
from datetime import date


class MilestoneCreate(BaseModel):
    title: str
    description: str | None = None
    guidline_end_date: date | None = None


class MilestoneUpdate(BaseModel):
    accomplished_date: date | None = None


class MilestoneResponse(BaseModel):
    id: int
    staff_id: int
    title: str
    description: str | None = None
    color: str
    status: bool
    created_at: str | None = None
    guidline_end_date: str | None = None
    accomplished_date: str | None = None

    class Config:
        from_attributes = True
```

**Step 2: EventCreate に milestone_id を追加**

既存 `EventCreate`（schemas.py 10-17 行目）を修正:

```python
class EventCreate(BaseModel):
    staff_id: int
    group: int
    start_time: str
    end_time: str
    title: str
    summary: str | None = None
    progress: str | None = None
    milestone_id: int | None = None
```

**Step 3: 構文チェック**

```bash
source .venv/bin/activate
python -c "from app.schemas import MilestoneCreate, MilestoneUpdate, MilestoneResponse, EventCreate; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add app/schemas.py
git commit -m "feat: add MilestoneCreate/Update/Response schemas and milestone_id to EventCreate"
```

---

### Task 3: /milestone/add エンドポイント

**Objective:** マイルストーン作成 API を追加する。admin のみ実行可能。被り回避カラー選択付き。

**Files:**
- Modify: `app/routers/timetable.py`
- Test: `tests/test_milestones.py`（新規）

**Step 1: failing test を書く**

`tests/test_milestones.py` を新規作成:

```python
from datetime import date

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database_base import Base, get_db

# テスト用インメモリDB
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# テスト前にテーブル作成
Base.metadata.create_all(bind=test_engine)


def test_add_milestone_as_admin():
    """admin=True のユーザーがマイルストーンを作成できる"""
    from app.tokens import create_access_token
    from app.models import StaffLogin

    db = TestSession()
    try:
        admin = StaffLogin(1, "admin", True)
        admin.STAFFID = 1
        db.add(admin)
        db.commit()
    finally:
        db.close()

    token = create_access_token(1, 1, True)

    response = client.post(
        "/milestone/add",
        json={"title": "Test Milestone", "description": "Test description"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Milestone"
    assert data["description"] == "Test description"
    assert data["status"] is True
    assert "color" in data
    assert data["color"] in [
        "#9c27b0", "#009688", "#795548", "#607d8b", "#e91e63",
        "#3f51b5", "#00bcd4", "#ff5722", "#8bc34a", "#ff9800",
    ]


def test_add_milestone_as_non_admin():
    """admin=False のユーザーはマイルストーンを作成できない"""
    from app.tokens import create_access_token
    from app.models import StaffLogin

    db = TestSession()
    try:
        admin = StaffLogin(2, "user", False)
        admin.STAFFID = 2
        db.add(admin)
        db.commit()
    finally:
        db.close()

    token = create_access_token(2, 1, False)

    response = client.post(
        "/milestone/add",
        json={"title": "Test Milestone"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
```

**Step 2: テストが fail することを確認**

```bash
source .venv/bin/activate
uv run pytest tests/test_milestones.py::test_add_milestone_as_admin -v
```

Expected: FAIL（`/milestone/add` が存在しないので 404）

**Step 3: エンドポイントを実装**

`app/routers/timetable.py` の import を修正:

```python
from ..models import StaffLogin, Team, User, EventORM, MilestoneORM
from ..schemas import EventCreate, EventUpdate, MilestoneCreate, MilestoneUpdate, MilestoneResponse
from datetime import date
```

末尾に追加:

```python
COLOR_OPTIONS = [
    "#9c27b0", "#009688", "#795548", "#607d8b", "#e91e63",
    "#3f51b5", "#00bcd4", "#ff5722", "#8bc34a", "#ff9800",
]


@router.post("/milestone/add", status_code=201)
def add_milestone(
    body: MilestoneCreate,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    if not claims.get("admin"):
        raise HTTPException(status_code=403, detail="admin only")
    # open milestone の色を調べて被らない色を選ぶ
    open_colors = {
        m[0] for m in db.query(MilestoneORM.color).filter(
            MilestoneORM.status == True
        ).all()
    }
    chosen = next(c for c in COLOR_OPTIONS if c not in open_colors)

    milestone = MilestoneORM(
        staff_id=claims["user_id"],
        title=body.title,
        description=body.description,
        color=chosen,
        guidline_end_date=body.guidline_end_date,
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone.to_dict()
```

**Step 4: テストが pass することを確認**

```bash
source .venv/bin/activate
uv run pytest tests/test_milestones.py -v
```

Expected: 2 passed

**Step 5: Commit**

```bash
git add app/routers/timetable.py tests/test_milestones.py
git commit -m "feat: add /milestone/add endpoint with admin-only access and color conflict resolution"
```

---

### Task 4: /milestone/all エンドポイント

**Objective:** すべての open milestone を取得する API を追加する。

**Files:**
- Modify: `app/routers/timetable.py`
- Test: `tests/test_milestones.py`

**Step 1: failing test を追加**

`tests/test_milestones.py` の既存テストの後に追加:

```python
def test_get_all_milestones():
    """open されているマイルストーン一覧を返す"""
    from app.tokens import create_access_token
    from app.models import StaffLogin, MilestoneORM

    db = TestSession()
    try:
        admin = StaffLogin(3, "admin", True)
        admin.STAFFID = 3
        db.add(admin)
        db.commit()

        m1 = MilestoneORM(
            staff_id=3, title="M1", color="#9c27b0", status=True,
            created_at=date(2026, 8, 20),
        )
        m2 = MilestoneORM(
            staff_id=3, title="M2", color="#009688", status=True,
            created_at=date(2026, 8, 21),
        )
        db.add_all([m1, m2])
        db.commit()
    finally:
        db.close()

    token = create_access_token(3, 1, True)

    response = client.get("/milestone/all", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(m["status"] is True for m in data)
```

**Step 2: テストが fail することを確認**

```bash
source .venv/bin/activate
uv run pytest tests/test_milestones.py::test_get_all_milestones -v
```

Expected: FAIL

**Step 3: エンドポイントを実装**

`app/routers/timetable.py` 末尾に追加:

```python
@router.get("/milestone/all")
def get_all_milestones(
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    milestones = db.query(MilestoneORM).filter(
        MilestoneORM.status == True
    ).all()
    return [m.to_dict() for m in milestones]
```

**Step 4: テストが pass することを確認**

```bash
source .venv/bin/activate
uv run pytest tests/test_milestones.py -v
```

Expected: 3 passed

**Step 5: Commit**

```bash
git add app/routers/timetable.py tests/test_milestones.py
git commit -m "feat: add /milestone/all endpoint returning open milestones"
```

---

### Task 5: /milestone/update エンドポイント（close）

**Objective:** `accomplished_date` を設定して milestone を close する API を追加する。
- 一度 closed したら再 open 不可
- close 時、属する全イベントの `completed` を `True` に自動更新

**Files:**
- Modify: `tests/test_milestones.py`
- Modify: `app/routers/timetable.py`

**Step 1: failing test を追加**

```python
def test_update_milestone_closes_it():
    """accomplished_date を設定すると milestone が closed になる"""
    from app.tokens import create_access_token
    from app.models import StaffLogin, MilestoneORM

    db = TestSession()
    try:
        admin = StaffLogin(4, "admin", True)
        admin.STAFFID = 4
        db.add(admin)
        db.commit()

        m = MilestoneORM(
            staff_id=4, title="M-Close", color="#607d8b", status=True,
            created_at=date(2026, 8, 20),
        )
        db.add(m)
        db.commit()
        milestone_id = m.id
    finally:
        db.close()

    token = create_access_token(4, 1, True)

    response = client.post(
        f"/milestone/update/{milestone_id}",
        json={"accomplished_date": "2026-08-20"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] is False
    assert data["accomplished_date"] == "2026-08-20"


def test_update_milestone_sets_events_completed():
    """マイルストーン close 時、属する全イベントの completed が True になる"""
    from app.tokens import create_access_token
    from app.models import StaffLogin, MilestoneORM, EventORM
    from datetime import datetime

    db = TestSession()
    try:
        admin = StaffLogin(5, "admin", True)
        admin.STAFFID = 5
        db.add(admin)
        db.commit()

        m = MilestoneORM(
            staff_id=5, title="M-Complete", color="#e91e63", status=True,
            created_at=date(2026, 8, 20),
        )
        db.add(m)
        db.commit()
        milestone_id = m.id

        e = EventORM(
            staff_id=5, group_id=1,
            start_time=datetime(2026, 9, 1, 9, 0),
            end_time=datetime(2026, 9, 1, 10, 0),
            title="Test Event", milestone_id=milestone_id, completed=False,
        )
        db.add(e)
        db.commit()
        event_id = e.id
    finally:
        db.close()

    token = create_access_token(5, 1, True)

    # milestone を close
    response = client.post(
        f"/milestone/update/{milestone_id}",
        json={"accomplished_date": "2026-08-20"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    # イベントの completed が True になっているか
    db2 = TestSession()
    try:
        evt = db2.query(EventORM).filter(EventORM.id == event_id).first()
        assert evt is not None
        assert evt.completed is True
    finally:
        db2.close()
```

**Step 2: テストが fail することを確認**

```bash
source .venv/bin/activate
uv run pytest tests/test_milestones.py::test_update_milestone_closes_it -v
```

Expected: FAIL

**Step 3: エンドポイントを実装**

```python
@router.post("/milestone/update/{milestone_id}")
def update_milestone(
    milestone_id: int,
    body: MilestoneUpdate,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    milestone = db.query(MilestoneORM).filter(
        MilestoneORM.id == milestone_id
    ).first()
    if milestone is None:
        raise HTTPException(status_code=404, detail="milestone not found")
    if not claims.get("admin"):
        raise HTTPException(status_code=403, detail="admin only")

    if body.accomplished_date is not None:
        milestone.accomplished_date = body.accomplished_date
        milestone.status = False
        # 属する全イベントの completed を True に自動更新
        db.query(EventORM).filter(
            EventORM.milestone_id == milestone_id
        ).update({"completed": True}, synchronize_session="fetch")

    db.commit()
    db.refresh(milestone)
    return milestone.to_dict()
```

**Step 4: テストが pass することを確認**

```bash
source .venv/bin/activate
uv run pytest tests/test_milestones.py -v
```

Expected: 5 passed

**Step 5: Commit**

```bash
git add app/routers/timetable.py tests/test_milestones.py
git commit -m "feat: add /milestone/update endpoint to close milestone with auto-complete"
```

---

### Task 6: /milestone/remove エンドポイント

**Objective:** マイルストーンを削除する API を追加する。

**Files:**
- Modify: `tests/test_milestones.py`
- Modify: `app/routers/timetable.py`

**Step 1: failing test を追加**

```python
def test_remove_milestone():
    """admin のみがマイルストーンを削除できる"""
    from app.tokens import create_access_token
    from app.models import StaffLogin, MilestoneORM

    db = TestSession()
    try:
        admin = StaffLogin(6, "admin", True)
        admin.STAFFID = 6
        db.add(admin)
        db.commit()

        m = MilestoneORM(
            staff_id=6, title="M-Delete", color="#3f51b5", status=True,
            created_at=date(2026, 8, 20),
        )
        db.add(m)
        db.commit()
        milestone_id = m.id
    finally:
        db.close()

    token = create_access_token(6, 1, True)

    response = client.delete(
        f"/milestone/remove/{milestone_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": milestone_id}

    # 削除済み確認
    db2 = TestSession()
    try:
        m2 = db2.query(MilestoneORM).filter(
            MilestoneORM.id == milestone_id
        ).first()
        assert m2 is None
    finally:
        db2.close()
```

**Step 2: テストが fail することを確認**

```bash
source .venv/bin/activate
uv run pytest tests/test_milestones.py::test_remove_milestone -v
```

Expected: FAIL

**Step 3: エンドポイントを実装**

```python
@router.delete("/milestone/remove/{milestone_id}")
def remove_milestone(
    milestone_id: int,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    milestone = db.query(MilestoneORM).filter(
        MilestoneORM.id == milestone_id
    ).first()
    if milestone is None:
        raise HTTPException(status_code=404, detail="milestone not found")
    if not claims.get("admin"):
        raise HTTPException(status_code=403, detail="admin only")
    db.delete(milestone)
    db.commit()
    return {"deleted": milestone_id}
```

**Step 4: テストが pass することを確認**

```bash
source .venv/bin/activate
uv run pytest tests/test_milestones.py -v
```

Expected: 6 passed

**Step 5: Commit**

```bash
git add app/routers/timetable.py tests/test_milestones.py
git commit -m "feat: add /milestone/remove endpoint for admin-only deletion"
```

---

### Task 7: EventCreate に milestone_id を通す

**Objective:** 既存 `/event/add` で `milestone_id` と `completed` を扱えるようにする。

**Files:**
- Modify: `app/routers/timetable.py`
- Test: `tests/test_milestones.py`

**Step 1: failing test を追加**

```python
def test_create_event_with_milestone():
    """イベント作成時に milestone_id を指定できる"""
    from app.tokens import create_access_token
    from app.models import StaffLogin, MilestoneORM
    from datetime import datetime

    db = TestSession()
    try:
        admin = StaffLogin(7, "admin", True)
        admin.STAFFID = 7
        db.add(admin)
        db.commit()

        m = MilestoneORM(
            staff_id=7, title="M-Event", color="#00bcd4", status=True,
            created_at=date(2026, 8, 20),
        )
        db.add(m)
        db.commit()
        milestone_id = m.id
    finally:
        db.close()

    token = create_access_token(7, 1, True)

    response = client.post(
        "/event/add",
        json={
            "staff_id": 7,
            "group": 1,
            "start_time": "2026-09-01T09:00:00.000Z",
            "end_time": "2026-09-01T10:00:00.000Z",
            "title": "Event with Milestone",
            "milestone_id": milestone_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["milestone_id"] == milestone_id
    assert data["completed"] is False


def test_event_to_dict_includes_milestone_fields():
    """EventORM.to_dict() に milestone_id と completed が含まれる"""
    from app.models import MilestoneORM, EventORM

    m = MilestoneORM(
        staff_id=1, title="Test", color="#9c27b0", status=True,
        created_at=date(2026, 8, 20),
    )
    e = EventORM(
        staff_id=1, group_id=1,
        start_time=datetime(2026, 9, 1, 9, 0),
        end_time=datetime(2026, 9, 1, 10, 0),
        title="Test Event", milestone_id=m.id, completed=True,
    )
    d = e.to_dict()
    assert "milestone_id" in d
    assert "completed" in d
    assert d["milestone_id"] == m.id
    assert d["completed"] is True
```

**Step 2: テストが fail することを確認**

```bash
source .venv/bin/activate
uv run pytest tests/test_milestones.py::test_event_to_dict_includes_milestone_fields -v
```

Expected: FAIL（`to_dict()` に milestone_id/completed がない）

**Step 3: `/event/add` を修正**

既存の `append_event_item` 関数（timetable.py 125-144 行目）に 2 行追加:

```python
@router.post("/event/add", status_code=201)
def append_event_item(
    body: EventCreate,
    claims: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    print(f"Insert 前: {body.start_time}")
    event = EventORM(
        staff_id=body.staff_id,
        group_id=body.group,
        start_time=convert_str_to_date(body.start_time),
        end_time=convert_str_to_date(body.end_time),
        title=body.title,
        summary=body.summary,
        progress=body.progress,
        milestone_id=body.milestone_id,
        completed=False,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event.to_dict()
```

**Step 4: テストが pass することを確認**

```bash
source .venv/bin/activate
uv run pytest tests/test_milestones.py -v
```

Expected: 8 passed

**Step 5: 既存テストが壊れていないか確認**

```bash
source .venv/bin/activate
uv run pytest tests/test_timetable.py -v
```

Expected: 既存テストは全て pass

**Step 6: Commit**

```bash
git add app/routers/timetable.py tests/test_milestones.py
git commit -m "feat: pass milestone_id and completed through /event/add"
```

---

## 最終確認

```bash
source .venv/bin/activate
uv run pytest tests/ -v
```

Expected: 全テスト pass

---

## リスク・トレードオフ

1. **DB マイグレーションは手動。** 実装は完了しても DB 上にテーブルがないと API は動作しない。ユーザーが Alembic で migration を実行する必要がある。
2. **`staff_id` FK。** 現時点で `M_LOGGININFO.STAFFID`。氏名表示に `M_STAFFINFO` が必要になったら変更可能。
3. **10 件超えのカラー cyclic。** 10 件超えた場合は 1 番目の色から cyclic に戻る（10 件を超えることはまずない前提）。
4. **テストの DB 共有。** テストでは `TestSession` を共有しているため、テスト間のデータの混入を防ぐため各テストで適切な初期化を行う。
5. **`completed` 自動更新。** マイルストーン close 時に属する全イベントの `completed` を `True` に更新。この処理はトランザクション内で実行される。

---

## 変更予定ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `app/models.py` | `M_MILESTONE` テーブル追加、`EventORM` に milestone_id/completed 追加 |
| `app/schemas.py` | `MilestoneCreate/Update/Response` 追加、`EventCreate` に milestone_id 追加 |
| `app/routers/timetable.py` | `/milestone/add`, `/milestone/all`, `/milestone/update`, `/milestone/remove` 追加、`/event/add` に milestone_id 対応 |
| `tests/test_milestones.py` | 新規作成（全テスト） |

---

**完了条件:** `uv run pytest tests/ -v` が全て pass する。
