def test_login_page_get(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert "サインイン" in r.text


def test_login_success_sets_session(client):
    r = client.post(
        "/login",
        data={"STAFFID": "1001", "PASSWORD": "secret"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    set_cookie = r.headers.get("set-cookie", "")
    assert "session=" in set_cookie
    assert "httponly" in set_cookie.lower()


def test_login_wrong_password(client):
    r = client.post(
        "/login", data={"STAFFID": "1001", "PASSWORD": "wrong"}
    )
    assert r.status_code == 400
    assert "違います" in r.text


def test_index_requires_login(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"] == "/login"


def test_logout_clears_session(client):
    r = client.post(
        "/login",
        data={"STAFFID": "1001", "PASSWORD": "secret"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    r = client.post("/logout", follow_redirects=False)
    assert r.status_code in (302, 303)

    r2 = client.get("/", follow_redirects=False)
    assert r2.status_code in (302, 303)
    assert r2.headers["location"] == "/login"