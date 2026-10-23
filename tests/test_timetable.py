import jwt

from app import tokens


def _login(client):
    return client.post(
        "/login",
        data={"STAFFID": "1001", "PASSWORD": "secret"},
        follow_redirects=True,
    )


def test_timetable_auth_sets_http_only_cookies(client):
    _login(client)
    r = client.get("/timetable/auth", follow_redirects=False)
    assert r.status_code == 303
    set_cookie = r.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "refresh_token=" in set_cookie
    assert "httponly" in set_cookie.lower()


def test_timetable_inquiry_requires_token(client):
    r = client.get("/timetable/inquiry", follow_redirects=False)
    assert r.status_code == 401


def test_timetable_inquiry_returns_admin(client):
    _login(client)
    client.get("/timetable/auth", follow_redirects=False)
    r = client.get("/timetable/inquiry", follow_redirects=False)
    assert r.status_code == 200
    body = r.json()
    assert body["admin"] is True
    assert "staff_id" in body


def test_inquiry_has_group_name_and_admin(client):
    _login(client)
    client.get("/timetable/auth", follow_redirects=False)
    r = client.get("/timetable/inquiry", follow_redirects=False)
    assert r.status_code == 200
    body = r.json()
    assert body["group_name"] == "SHORT_A"
    assert body["admin"] is True


def test_event_all(client):
    _login(client)
    client.get("/timetable/auth", follow_redirects=False)
    r = client.get("/event/all", follow_redirects=False)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_group_names(client):
    _login(client)
    client.get("/timetable/auth", follow_redirects=False)
    r = client.get("/group-names", follow_redirects=False)
    assert r.status_code == 200
    assert r.json() == ["SHORT_A"]


def test_group_users(client):
    _login(client)
    client.get("/timetable/auth", follow_redirects=False)
    r = client.get("/group/users", follow_redirects=False)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_event_add(client):
    _login(client)
    client.get("/timetable/auth", follow_redirects=False)
    r = client.post(
        "/event/add",
        json={
            "staff_id": 1001,
            "group": 3,
            "start_time": "2026-08-02T10:00:00.000Z",
            "end_time": "2026-08-02T11:00:00.000Z",
            "title": "new event",
        },
        follow_redirects=False,
    )
    assert r.status_code == 201
    r2 = client.get("/event/all", follow_redirects=False)
    assert len(r2.json()) == 2


def test_event_update(client):
    _login(client)
    client.get("/timetable/auth", follow_redirects=False)
    r = client.post("/event/update/1", json={"summary": "s2", "progress": "done"})
    assert r.status_code == 200
    r2 = client.get("/event/all", follow_redirects=False)
    ev = r2.json()[0]
    assert ev["summary"] == "s2"
    assert ev["progress"] == "done"


def test_event_remove(client):
    _login(client)
    client.get("/timetable/auth", follow_redirects=False)
    r = client.delete("/event/remove/1")
    assert r.status_code == 200
    r2 = client.get("/event/all", follow_redirects=False)
    assert len(r2.json()) == 0


def test_date_update_moves_event_times(client):
    # cookie ログインのセッション確立は環境依存で不安定なため、Bearer トークンで直接検証する
    # （test_bearer_header_only_allows_event_all と同じ方式）。
    access = tokens.create_access_token(1001, 3, True)
    r = client.post(
        "/date/update",
        headers=_bearer(access),
        json={
            "data": [
                {
                    "id": 1,
                    "start_time": "2026-08-02T14:00:00.000Z",
                    "end_time": "2026-08-02T15:00:00.000Z",
                }
            ]
        },
        follow_redirects=False,
    )
    assert r.status_code == 200
    updated = r.json()
    assert isinstance(updated, list) and len(updated) == 1
    assert updated[0]["id"] == 1
    assert updated[0]["start"] == "2026-08-02T14:00:00.000Z"
    assert updated[0]["end"] == "2026-08-02T15:00:00.000Z"


def test_date_update_nonexistent_event_returns_404(client):
    access = tokens.create_access_token(1001, 3, True)
    r = client.post(
        "/date/update",
        headers=_bearer(access),
        json={"data": [{"id": 9999, "start_time": "x", "end_time": "y"}]},
        follow_redirects=False,
    )
    assert r.status_code == 404


def test_date_update_requires_token(client):
    r = client.post("/date/update", json={"data": []}, follow_redirects=False)
    assert r.status_code == 401


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_bearer_header_only_allows_event_all(client):
    # Cookie 無しでも Authorization: Bearer ヘッダーだけで認可される
    access = tokens.create_access_token(1001, 3, True)
    r = client.get("/event/all", headers=_bearer(access), follow_redirects=False)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_bearer_header_lowercase_bearer_allowed(client):
    access = tokens.create_access_token(1001, 3, True)
    r = client.get(
        "/event/all",
        headers={"Authorization": f"bearer {access}"},
        follow_redirects=False,
    )
    assert r.status_code == 200


def test_timetable_auth_location_has_token_param(client):
    _login(client)
    r = client.get("/timetable/auth", follow_redirects=False)
    assert r.status_code == 303
    assert "?token=" in r.headers["location"]


def test_refresh_with_bearer_returns_access_token_body(client):
    refresh = tokens.create_refresh_token(1001, 3, True)
    r = client.post("/refresh", headers=_bearer(refresh), follow_redirects=False)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "access_token" in body
    claims = jwt.decode(body["access_token"], tokens.SECRET_KEY, algorithms=[tokens.ALGORITHM])
    assert claims["type"] == "access"
    assert claims["user_id"] == 1001


def test_refresh_with_access_bearer_is_allowed(client):
    # 旧 Flask 契約: 呼び出し側 (time-table-to-line) はアクセストークンを Bearer で /refresh に
    # 送る。access type でも受理し、新しいアクセストークン文字列を body で返すこと。
    access = tokens.create_access_token(1001, 3, True)
    r = client.post("/refresh", headers=_bearer(access), follow_redirects=False)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "access_token" in body
    claims = jwt.decode(body["access_token"], tokens.SECRET_KEY, algorithms=[tokens.ALGORITHM])
    assert claims["type"] == "access"
    assert claims["user_id"] == 1001


def test_refresh_missing_token_returns_401(client):
    r = client.post("/refresh", follow_redirects=False)
    assert r.status_code == 401


def test_event_update_progress_null_clears(client):
    # Issue #44 (受入 2): progress に一度値を入れた後、null で解除できるか。
    _login(client)
    client.get("/timetable/auth", follow_redirects=False)
    # 値を設定
    r = client.post("/event/update/1", json={"progress": "done"})
    assert r.status_code == 200
    assert r.json()["progress"] == "done"
    # null で解除
    r2 = client.post("/event/update/1", json={"progress": None})
    assert r2.status_code == 200
    assert r2.json()["progress"] is None
    # DB 反映を GET 側でも確認
    ev = client.get("/event/all", follow_redirects=False).json()[0]
    assert ev["progress"] is None


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
    # conftest の event 1 は staff_id=1001 所有。非 admin の別ユーザー 1002 は更新不可。
    other = tokens.create_access_token(1002, 3, False)
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
    owner = tokens.create_access_token(1002, 3, False)
    event_id = _add_event_staff(client, admin, 1002)

    r = client.post(
        f"/event/update/{event_id}",
        headers=_bearer(owner),
        json={"summary": "mine"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert r.json()["summary"] == "mine"


def test_event_update_admin_can_modify_others(client):
    # admin は他人のイベントも更新できる（ユーザー要件: admin は例外）。
    admin = tokens.create_access_token(1001, 3, True)
    event_id = _add_event_staff(client, admin, 1002)

    r = client.post(
        f"/event/update/{event_id}",
        headers=_bearer(admin),
        json={"summary": "by-admin"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert r.json()["summary"] == "by-admin"


def test_event_remove_other_members_event_forbidden(client):
    other = tokens.create_access_token(1002, 3, False)
    r = client.delete("/event/remove/1", headers=_bearer(other), follow_redirects=False)
    assert r.status_code == 403
    # 削除が拒否されイベントが残っていること
    remaining = [
        e["id"]
        for e in client.get(
            "/event/all", headers=_bearer(other), follow_redirects=False
        ).json()
    ]
    assert 1 in remaining


def test_event_remove_owner_non_admin_allowed(client):
    admin = tokens.create_access_token(1001, 3, True)
    owner = tokens.create_access_token(1002, 3, False)
    event_id = _add_event_staff(client, admin, 1002)

    r = client.delete(
        f"/event/remove/{event_id}", headers=_bearer(owner), follow_redirects=False
    )
    assert r.status_code == 200
    assert r.json()["deleted"] == event_id


def test_event_remove_admin_can_remove_others(client):
    admin = tokens.create_access_token(1001, 3, True)
    event_id = _add_event_staff(client, admin, 1002)

    r = client.delete(
        f"/event/remove/{event_id}", headers=_bearer(admin), follow_redirects=False
    )
    assert r.status_code == 200
    assert r.json()["deleted"] == event_id


def test_date_update_other_members_event_forbidden(client):
    other = tokens.create_access_token(1002, 3, False)
    r = client.post(
        "/date/update",
        headers=_bearer(other),
        json={"data": [{"id": 1, "start_time": "x", "end_time": "y"}]},
        follow_redirects=False,
    )
    assert r.status_code == 403


def test_date_update_admin_can_move_others_event(client):
    admin = tokens.create_access_token(1001, 3, True)
    event_id = _add_event_staff(client, admin, 1002)

    r = client.post(
        "/date/update",
        headers=_bearer(admin),
        json={
            "data": [
                {
                    "id": event_id,
                    "start_time": "2026-08-02T14:00:00.000Z",
                    "end_time": "2026-08-02T15:00:00.000Z",
                }
            ]
        },
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert r.json()[0]["id"] == event_id
