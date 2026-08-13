import jwt

from app import tokens
from app.config import SECRET_KEY


def _claims(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[tokens.ALGORITHM])


def test_access_token_payload_has_admin_and_type():
    t = tokens.create_access_token(1001, 3, True)
    c = _claims(t)
    assert c["user_id"] == 1001
    assert c["group_id"] == 3
    assert c["admin"] is True
    assert c["type"] == "access"
    assert "exp" in c


def test_refresh_token_has_type_refresh():
    c = _claims(tokens.create_refresh_token(1001, 3, False))
    assert c["type"] == "refresh"
    assert c["admin"] is False
