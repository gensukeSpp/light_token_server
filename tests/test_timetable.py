def _login(client):
    return client.post(
        "/login",
        data={"STAFFID": "1001", "PASSWORD": "secret"},
        follow_redirects=False,
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