# Issue #20 実装タスク（1/2：更新・削除の RED → GREEN）— 所有権チェック

> タスク続き（Task 4–6）は同じディレクトリの `tasks2.md` を参照。

前提（セッション最初に 1 回だけ）:
```bash
cd /home/nabu_dvl/workspace/the-calendar-to-timeline/light_token_server
source .venv/bin/activate
```

ベースライン: `python -m pytest -q` → **79 passed**。終了時は 79 + 追加 8 = **87 passed**。

判定ポリシー（全エンドポイント共通）: イベントの**作成者本人**または **admin** のみ更新・削除可。
共通ヘルパー `_require_event_owner_or_admin(target, claims)` を使う。

---

### Task 1: `update_event_item` の権限テスト追加（RED）

**Objective:** `/event/update/{id}` が「本人 or admin」のみ許可され、他人のイベントを非 admin が更新すると 403 になる既存欠陥をテストで固定する。

**Files:** Modify `tests/test_timetable.py`（末尾に追記）

**Step 1:** 末尾に次のテストを追加。

```python
# ===== Issue #20: 更新・削除の所有者チェック（本人 or admin）=====

def _add_event_staff(client, admin_token, staff_id) -> int:
    """admin 権限で任意 staff_id のイベントを作成し、その id を返す。"""
    r = client.post(
        "/event/add",
        headers=_bearer(admin_token),
        json={
            "staff_id": staff_id,
            "group": 3,
            "start_time": "2026-08-02T10:00:00.000Z",
            "end_time": "2026-08-02T11:00:00.000Z",
            "title": "other",
        },
        follow_redirects=False,
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_event_update_other_members_event_forbidden(client):
    # conftest の event 1 は staff_id=1001 所有。非 admin の別ユーザー 9999 は更新不可。
    other = tokens.create_access_token(9999, 3, False)
    r = client.post(
        "/event/update/1",
        headers=_bearer(other),
        json={"summary": "hacked"},
        follow_redirects=False,
    )
    assert r.status_code == 403


def test_event_update_owner_non_admin_allowed(client):
    # 非 admin でも本人のイベントは更新できる。
    admin = tokens.create_access_token(1001, 3, True)
    owner = tokens.create_access_token(9999, 3, False)
    event_id = _add_event_staff(client, admin, 9999)

    r = client.post(
        f"/event/update/{event_id}",
        headers=_bearer(owner),
        json={"title": "mine"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert r.json()["title"] == "mine"


def test_event_update_admin_can_modify_others(client):
    # admin は他人のイベントも更新できる（ユーザー要件: admin は例外）。
    admin = tokens.create_access_token(1001, 3, True)
    event_id = _add_event_staff(client, admin, 9999)

    r = client.post(
        f"/event/update/{event_id}",
        headers=_bearer(admin),
        json={"title": "by-admin"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert r.json()["title"] == "by-admin"
```

**Step 2:** 失敗を確認（未チェックのため、403 期待が 200 になり落ちる）。

```bash
python -m pytest tests/test_timetable.py::test_event_update_other_members_event_forbidden -q
python -m pytest tests/test_timetable.py::test_event_update_owner_non_admin_allowed -q
```
Expected: FAIL — 1 つ目は現状 200 が返り 403 にならない。

---

### Task 2: 共通ヘルパー追加 + `update_event_item` へ適用（GREEN）

**Objective:** 判定を 1 関数に集約し、`update_event_item` に適用して Task 1 をグリーン化する。

**Files:** Modify `app/routers/timetable.py`（`update_event_item` の直前・194 行付近にヘルパー追加、200 行付近に呼び出し）

**Step 1:** `update_event_item` の直前にヘルパーを追加。

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

**Step 2:** `update_event_item` の 404 チェック直後（`target is None` ブロックの後、203 行）に呼び出しを追加。

```python
    _require_event_owner_or_admin(target, claims)
```

**Step 3:** グリーン化を確認。

```bash
python -m pytest tests/test_timetable.py::test_event_update_other_members_event_forbidden -q
python -m pytest tests/test_timetable.py::test_event_update_owner_non_admin_allowed -q
python -m pytest tests/test_timetable.py::test_event_update_admin_can_modify_others -q
```
Expected: 3 つとも PASS（既存 `test_event_update` / `test_event_update_progress_null_clears` も本人&admin なので PASS のまま）。

---

### Task 3: `remove_event_item` の権限テスト追加（RED）

**Objective:** `/event/remove/{id}` も「本人 or admin」のみ許可されることをテストで固定する。

**Files:** Modify `tests/test_timetable.py`（Task 1 の末尾に続けて追加）

**Step 1:** 末尾に追加。

```python
def test_event_remove_other_members_event_forbidden(client):
    other = tokens.create_access_token(9999, 3, False)
    r = client.delete("/event/remove/1", headers=_bearer(other), follow_redirects=False)
    assert r.status_code == 403
    # 削除が拒否されイベントが残っていること
    remaining = [e["id"] for e in client.get("/event/all", headers=_bearer(other), follow_redirects=False).json()]
    assert 1 in remaining


def test_event_remove_owner_non_admin_allowed(client):
    admin = tokens.create_access_token(1001, 3, True)
    owner = tokens.create_access_token(9999, 3, False)
    event_id = _add_event_staff(client, admin, 9999)

    r = client.delete(f"/event/remove/{event_id}", headers=_bearer(owner), follow_redirects=False)
    assert r.status_code == 200
    assert r.json()["deleted"] == event_id


def test_event_remove_admin_can_remove_others(client):
    admin = tokens.create_access_token(1001, 3, True)
    event_id = _add_event_staff(client, admin, 9999)

    r = client.delete(f"/event/remove/{event_id}", headers=_bearer(admin), follow_redirects=False)
    assert r.status_code == 200
    assert r.json()["deleted"] == event_id
```

**Step 2:** 失敗を確認。

```bash
python -m pytest tests/test_timetable.py::test_event_remove_other_members_event_forbidden -q
```
Expected: FAIL — 現状 200 で削除されるため 403 にならず、`1 in remaining` も偽。