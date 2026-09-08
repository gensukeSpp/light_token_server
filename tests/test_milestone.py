"""統合テスト: /milestone/* API と /event/* の milestone_id / completed 反映。

既存 test_timetable.py のセッションクッキーまわり 10 件はベースから既に失敗しているため、
本テストはその影響を受けないよう Bearer トークンを直接生成して送る方式を使う。
"""

import datetime

import jwt

from app import tokens
from app.jobs.close_milestones import close_expired_waiting_milestones
from app.models import MILESTONE_CLOSED, MILESTONE_OPEN, MILESTONE_WAITING, MilestoneORM
from app.routers.timetable import MILESTONE_COLORS


def _bearer(admin: bool = True) -> dict:
    access = tokens.create_access_token(1001, 3, admin)
    return {"Authorization": f"Bearer {access}"}


def _add(client, title="M1", **extra):
    return client.post("/milestone/add", json={"title": title, **extra}, headers=_bearer(True))


def _add_event(client, milestone_id=None, **extra):
    body = {
        "staff_id": 1001,
        "group": 3,
        "start_time": "2026-08-02T10:00:00.000Z",
        "end_time": "2026-08-02T11:00:00.000Z",
        "title": "child",
    }
    if milestone_id is not None:
        body["milestone_id"] = milestone_id
    body.update(extra)
    return client.post("/event/add", json=body, headers=_bearer(True))


# 1. マイルストーン追加(admin)
def test_milestone_add_admin(client):
    r = _add(client, "M1")
    assert r.status_code == 201
    body = r.json()
    assert body["color"] in MILESTONE_COLORS
    assert body["status"] == "open"
    assert body["staff_id"] == 1001


# 2. 色衝突回避: 1 件目 #9c27b0 → 2 件目は #009688 (MILESTONE_COLORS[1])
def test_milestone_add_avoids_used_color(client):
    r1 = _add(client, "M1")
    assert r1.status_code == 201
    assert r1.json()["color"] == MILESTONE_COLORS[0]
    r2 = _add(client, "M2")
    assert r2.status_code == 201
    assert r2.json()["color"] == MILESTONE_COLORS[1]


# 3. open 一覧: 作成後 1 件、close 後は 0 件
def test_milestone_all_returns_open_only(client):
    r = _add(client, "M1")
    assert r.status_code == 201
    ms_id = r.json()["id"]
    all_resp = client.get("/milestone/all", headers=_bearer(True))
    assert all_resp.status_code == 200
    rows = all_resp.json()
    assert len(rows) == 1
    assert rows[0]["title"] == "M1"
    assert rows[0]["status"] == "open"

    # accomplished_date 設定(waiting)後も一覧に出続ける (Issue #9: open + waiting)
    client.post(
        f"/milestone/update/{ms_id}",
        json={"accomplished_date": "2026-08-20"},
        headers=_bearer(True),
    )
    all_resp2 = client.get("/milestone/all", headers=_bearer(True))
    assert len(all_resp2.json()) == 1
    assert all_resp2.json()[0]["status"] == "waiting"


# 3b. Issue #9: /milestone/all は open + waiting の両方を含む(status != closed)
def test_milestone_all_includes_waiting(client):
    ms1 = _add(client, "M1").json()
    ms2 = _add(client, "M2").json()
    # M2 を waiting に
    client.post(
        f"/milestone/update/{ms2['id']}",
        json={"accomplished_date": "2026-08-20"},
        headers=_bearer(True),
    )
    rows = client.get("/milestone/all", headers=_bearer(True)).json()
    assert len(rows) == 2
    by_title = {r["title"]: r["status"] for r in rows}
    assert by_title["M1"] == "open"
    assert by_title["M2"] == "waiting"
    assert ms1["id"] in [r["id"] for r in rows]


# 4. 追加(非 admin) → 403
def test_milestone_add_non_admin_forbidden(client):
    r = client.post("/milestone/add", json={"title": "M1"}, headers=_bearer(False))
    assert r.status_code == 403


# 5. accomplished_date 設定: status=waiting、子イベント completed=True (close 相当)
def test_milestone_close_sets_completed(client):
    ms = _add(client, "M1")
    ms_id = ms.json()["id"]
    ev = _add_event(client, milestone_id=ms_id)
    assert ev.status_code == 201

    r = client.post(
        f"/milestone/update/{ms_id}",
        json={"accomplished_date": "2026-08-20"},
        headers=_bearer(True),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "waiting"

    events = client.get("/event/all", headers=_bearer(True)).json()
    child = next(e for e in events if e["milestone_id"] == ms_id)
    assert child["completed"] is True


# 6. waiting で再び accomplished_date 指定 → 200、status は waiting のまま (409 にならない)
def test_milestone_mark_accomplished_twice_keeps_waiting(client):
    ms = _add(client, "M1")
    ms_id = ms.json()["id"]
    r1 = client.post(
        f"/milestone/update/{ms_id}",
        json={"accomplished_date": "2026-08-20"},
        headers=_bearer(True),
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "waiting"
    r2 = client.post(
        f"/milestone/update/{ms_id}",
        json={"accomplished_date": "2026-08-21"},
        headers=_bearer(True),
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "waiting"
    assert r2.json()["accomplished_date"] == "2026-08-21"


# 7. 存在しない id → 404
def test_milestone_update_not_found(client):
    r = client.post(
        "/milestone/update/999",
        json={"accomplished_date": "2026-08-20"},
        headers=_bearer(True),
    )
    assert r.status_code == 404


# 8. 削除(admin) → 200 {"closed": id}、DB からは消えず status=closed、子イベント completed=True
def test_milestone_remove_closes_instead_of_delete(client):

    ms = _add(client, "M1")
    ms_id = ms.json()["id"]
    ev = _add_event(client, milestone_id=ms_id)
    assert ev.status_code == 201
    ev_id = ev.json()["id"]

    r = client.delete(f"/milestone/remove/{ms_id}", headers=_bearer(True))
    assert r.status_code == 200
    assert r.json() == {"closed": ms_id}

    # マイルストーンは残る（open 一覧には出ない）
    rows = client.get("/milestone/all", headers=_bearer(True)).json()
    assert len(rows) == 0

    events = client.get("/event/all", headers=_bearer(True)).json()
    child = next(e for e in events if e["id"] == ev_id)
    assert child["milestone_id"] == ms_id  # 子イベントは残る（削除で切り離さない）
    assert child["completed"] is True


# 9. /event/add に milestone_id → 201、to_dict に milestone_id が入る
def test_event_add_accepts_milestone_id(client):
    ms = _add(client, "M1")
    ms_id = ms.json()["id"]
    r = _add_event(client, milestone_id=ms_id)
    assert r.status_code == 201
    assert r.json()["milestone_id"] == ms_id


# 10. /event/update/1 に completed=True → 200、completed が True
def test_event_update_sets_completed(client):
    r = client.post("/event/update/1", json={"completed": True}, headers=_bearer(True))
    assert r.status_code == 200
    assert r.json()["completed"] is True


# --- Issue #9: update 編集対応 & waiting 遷移 ---

# 11. title のみ編集 → 200、title 反映、status は open のまま (accomplished_date 未指定)
def test_milestone_update_edits_title_only(client):
    ms = _add(client, "M1")
    ms_id = ms.json()["id"]
    r = client.post(
        f"/milestone/update/{ms_id}",
        json={"title": "renamed"},
        headers=_bearer(True),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "renamed"
    assert body["status"] == "open"
    assert body["accomplished_date"] is None


# 12. accomplished_date 設定 → 200、status は waiting (closed ではない)
def test_milestone_update_accomplished_sets_waiting(client):
    ms = _add(client, "M1")
    ms_id = ms.json()["id"]
    r = client.post(
        f"/milestone/update/{ms_id}",
        json={"accomplished_date": "2026-08-20"},
        headers=_bearer(True),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "waiting"
    assert body["accomplished_date"] == "2026-08-20"


# 13. waiting に accomplished_date=null を明示 → re-open(open)、accomplished_date は None
def test_milestone_reopen_from_waiting(client):
    ms = _add(client, "M1")
    ms_id = ms.json()["id"]
    client.post(
        f"/milestone/update/{ms_id}",
        json={"accomplished_date": "2026-08-20"},
        headers=_bearer(True),
    )
    r = client.post(
        f"/milestone/update/{ms_id}",
        json={"accomplished_date": None},
        headers=_bearer(True),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "open"
    assert body["accomplished_date"] is None


# 14. guideline_end_date / description 編集 → 反映される
def test_milestone_update_edits_meta(client):
    ms = _add(client, "M1")
    ms_id = ms.json()["id"]
    r = client.post(
        f"/milestone/update/{ms_id}",
        json={"description": "desc", "guideline_end_date": "2026-09-01"},
        headers=_bearer(True),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["description"] == "desc"
    assert body["guideline_end_date"] == "2026-09-01"
    assert body["status"] == "open"


# 15. closed 化(remove)後の再 update → 409 (契約: closed + any は拒否)
def test_milestone_update_after_closed_returns_409(client):
    ms = _add(client, "M1")
    ms_id = ms.json()["id"]
    r = client.delete(f"/milestone/remove/{ms_id}", headers=_bearer(True))
    assert r.status_code == 200
    assert r.json() == {"closed": ms_id}

    for body in (
        {"title": "renamed"},
        {"accomplished_date": "2026-08-20"},
        {"accomplished_date": None},
    ):
        resp = client.post(f"/milestone/update/{ms_id}", json=body, headers=_bearer(True))
        assert resp.status_code == 409, body


# 16. waiting 中のマイルストーンの色は「使用中」とみなし、新規作成は別色を選ぶ
def test_next_color_counts_waiting_as_used(client):
    ms = _add(client, "M1")
    ms_id = ms.json()["id"]
    first_color = ms.json()["color"]
    # waiting へ遷移しても色は解放されない
    client.post(
        f"/milestone/update/{ms_id}",
        json={"accomplished_date": "2026-08-20"},
        headers=_bearer(True),
    )
    r2 = _add(client, "M2")
    assert r2.status_code == 201
    assert r2.json()["color"] != first_color


# --- Task-11: グレース期間後の自動 closed 遷移 ---

TODAY = datetime.date(2026, 9, 10)


def _make_waiting(client, title, accomplished: str) -> int:
    """API 経由で waiting 状態のマイルストーンを作り、id を返す。"""
    ms = _add(client, title)
    assert ms.status_code == 201
    ms_id = ms.json()["id"]
    r = client.post(
        f"/milestone/update/{ms_id}",
        json={"accomplished_date": accomplished},
        headers=_bearer(True),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "waiting"
    return ms_id


def _set_accomplished_directly(factory, ms_id: int, accomplished: datetime.date):
    """テスト用: DB 直操作で accomplished_date を過去日付へ調整する。"""
    db = factory()
    try:
        ms = db.query(MilestoneORM).filter(MilestoneORM.id == ms_id).first()
        ms.accomplished_date = accomplished
        db.commit()
    finally:
        db.close()


def _status_of(factory, ms_id: int) -> str:
    db = factory()
    try:
        return (
            db.query(MilestoneORM)
            .filter(MilestoneORM.id == ms_id)
            .first()
            .status
        )
    finally:
        db.close()


# 17. 猶予内 (today - 3日) → 0 件、waiting のまま
def test_auto_close_before_grace(client, db_session_factory):
    ms_id = _make_waiting(client, "M1", "2026-09-07")  # API 契約確認用
    _set_accomplished_directly(db_session_factory, ms_id, TODAY - datetime.timedelta(days=3))
    n = close_expired_waiting_milestones(db_session_factory(), TODAY)
    assert n == 0
    assert _status_of(db_session_factory, ms_id) == MILESTONE_WAITING


# 18. 猶予超過 (today - 6日) → 1 件 closed
def test_auto_close_after_grace(client, db_session_factory):
    ms_id = _make_waiting(client, "M1", "2026-09-07")
    _set_accomplished_directly(db_session_factory, ms_id, TODAY - datetime.timedelta(days=6))
    n = close_expired_waiting_milestones(db_session_factory(), TODAY)
    assert n == 1
    assert _status_of(db_session_factory, ms_id) == MILESTONE_CLOSED


# 19. open / closed は対象外。waiting 超過のみ closed 化
def test_auto_close_only_waiting(client, db_session_factory):
    open_ms = _add(client, "OPEN_MS").json()
    closed_ms = _add(client, "CLOSED_MS").json()
    r = client.delete(f"/milestone/remove/{closed_ms['id']}", headers=_bearer(True))
    assert r.status_code == 200
    waiting_id = _make_waiting(client, "WAITING_MS", "2026-09-07")
    _set_accomplished_directly(db_session_factory, waiting_id, TODAY - datetime.timedelta(days=6))

    n = close_expired_waiting_milestones(db_session_factory(), TODAY)
    assert n == 1
    assert _status_of(db_session_factory, open_ms["id"]) == MILESTONE_OPEN
    assert _status_of(db_session_factory, closed_ms["id"]) == MILESTONE_CLOSED
    assert _status_of(db_session_factory, waiting_id) == MILESTONE_CLOSED


# 20. 子イベント completed は自動 closed で変更されない (True のまま)
def test_auto_close_keeps_completed(client, db_session_factory):
    ms = _add(client, "M1")
    assert ms.status_code == 201
    ms_id = ms.json()["id"]
    ev = _add_event(client, milestone_id=ms_id)
    assert ev.status_code == 201
    ev_id = ev.json()["id"]

    # waiting 遷移 (子イベント completed=True になる)
    r = client.post(
        f"/milestone/update/{ms_id}",
        json={"accomplished_date": "2026-09-07"},
        headers=_bearer(True),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "waiting"

    _set_accomplished_directly(db_session_factory, ms_id, TODAY - datetime.timedelta(days=6))
    assert close_expired_waiting_milestones(db_session_factory(), TODAY) == 1
    assert _status_of(db_session_factory, ms_id) == MILESTONE_CLOSED

    # 自動 closed では子イベント completed を変更しない (決定事項 3)
    events2 = client.get("/event/all", headers=_bearer(True)).json()
    child2 = next(e for e in events2 if e["id"] == ev_id)
    assert child2["completed"] is True
    assert child2["milestone_id"] == ms_id


# 21. 境界: accomplished_date + 5日 == today → 当日をもって closed (`<=` 採用)
def test_auto_close_boundary(client, db_session_factory):
    in_grace_id = _make_waiting(client, "IN_GRACE", "2026-09-07")
    _set_accomplished_directly(db_session_factory, in_grace_id, TODAY - datetime.timedelta(days=4))
    assert close_expired_waiting_milestones(db_session_factory(), TODAY) == 0
    assert _status_of(db_session_factory, in_grace_id) == MILESTONE_WAITING

    boundary_id = _make_waiting(client, "BOUNDARY", "2026-09-07")
    _set_accomplished_directly(db_session_factory, boundary_id, TODAY - datetime.timedelta(days=5))
    assert close_expired_waiting_milestones(db_session_factory(), TODAY) == 1
    assert _status_of(db_session_factory, boundary_id) == MILESTONE_CLOSED


# 22. accomplished_date が None (open) → 対象外。None を誤って閉じない
def test_auto_close_no_accomplished(client, db_session_factory):
    ms = _add(client, "M1")
    assert ms.status_code == 201
    ms_id = ms.json()["id"]
    n = close_expired_waiting_milestones(db_session_factory(), TODAY)
    assert n == 0
    assert _status_of(db_session_factory, ms_id) == MILESTONE_OPEN