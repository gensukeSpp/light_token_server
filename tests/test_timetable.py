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