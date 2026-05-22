from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from routes.v1 import auth as auth_routes
from schemas.auth import LoginRequest, RegisterRequest
from schemas.transaction import UserBalance
from schemas.user import UserResponse


def credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def encoded_token(secret: str, payload: dict) -> str:
    claims = {"exp": datetime.utcnow() + timedelta(minutes=1), **payload}
    return jwt.encode(claims, secret, algorithm=auth_routes.settings.ALGORITHM)


def fake_user(user_id=None):
    now = datetime.utcnow()
    return SimpleNamespace(
        id=user_id or uuid4(),
        email="person@example.com",
        password_hash="hashed",
        full_name="Person",
        currency="KZT",
        preferred_language="en",
        monthly_limit=100,
        daily_limit=10,
        created_at=now,
        updated_at=now,
    )


def test_decode_token_accepts_auth_and_legacy_secrets(monkeypatch):
    monkeypatch.setattr(auth_routes.settings, "JWT_SECRET", "auth-secret")
    monkeypatch.setattr(auth_routes.settings, "SECRET_KEY", "legacy-secret")

    assert auth_routes._decode_token(encoded_token("auth-secret", {"sub": "auth-user"}))["sub"] == "auth-user"
    assert auth_routes._decode_token(encoded_token("legacy-secret", {"sub": "legacy-user"}))["sub"] == "legacy-user"
    assert auth_routes._decode_token("invalid") is None


def test_get_jwt_payload_rejects_invalid_payload(monkeypatch):
    monkeypatch.setattr(auth_routes, "_decode_token", lambda _token: {})

    with pytest.raises(HTTPException) as exc_info:
        auth_routes.get_jwt_payload(credentials("missing-sub"))

    assert exc_info.value.status_code == 401


def test_current_user_dependencies(monkeypatch):
    monkeypatch.setattr(auth_routes.settings, "INTERNAL_API_TOKEN", "internal")

    assert auth_routes.get_user_internal_or_jwt("internal", "user-1", None, None) == "user-1"

    with pytest.raises(HTTPException, match="X-User-ID"):
        auth_routes.get_user_internal_or_jwt("internal", None, None, None)

    with pytest.raises(HTTPException, match="Not authenticated"):
        auth_routes.get_user_internal_or_jwt(None, None, None, None)

    monkeypatch.setattr(auth_routes, "_decode_token", lambda _token: None)
    with pytest.raises(HTTPException, match="Invalid authentication"):
        auth_routes.get_user_internal_or_jwt(None, None, credentials("bad"), None)

    monkeypatch.setattr(auth_routes, "_decode_token", lambda _token: {})
    with pytest.raises(HTTPException, match="Invalid authentication"):
        auth_routes.get_user_internal_or_jwt(None, None, credentials("missing-sub"), None)

    monkeypatch.setattr(auth_routes, "_decode_token", lambda _token: {"sub": "jwt-user"})
    assert auth_routes.get_user_internal_or_jwt(None, None, credentials("ok"), None) == "jwt-user"
    assert auth_routes.get_current_user({"sub": "jwt-user"}) == "jwt-user"


def test_register_and_login(monkeypatch):
    user = fake_user()
    request = RegisterRequest(
        email=user.email,
        password="secret",
        full_name=user.full_name,
        currency=user.currency,
        preferred_language=user.preferred_language,
    )
    monkeypatch.setattr(auth_routes, "create_access_token", lambda data: f"token:{data['sub']}")

    monkeypatch.setattr(auth_routes, "get_user_by_email", lambda _db, _email: user)
    with pytest.raises(HTTPException, match="Email already"):
        auth_routes.register(request, None)

    monkeypatch.setattr(auth_routes, "get_user_by_email", lambda _db, _email: None)
    monkeypatch.setattr(auth_routes, "create_user", lambda _db, _request: user)
    assert auth_routes.register(request, None).access_token == f"token:{user.id}"

    login = LoginRequest(email=user.email, password="secret")
    with pytest.raises(HTTPException, match="Incorrect email"):
        auth_routes.login(login, None)

    monkeypatch.setattr(auth_routes, "get_user_by_email", lambda _db, _email: user)
    monkeypatch.setattr(auth_routes, "verify_password", lambda _plain, _hashed: False)
    with pytest.raises(HTTPException, match="Incorrect email"):
        auth_routes.login(login, None)

    monkeypatch.setattr(auth_routes, "verify_password", lambda _plain, _hashed: True)
    assert auth_routes.login(login, None).access_token == f"token:{user.id}"


def test_profile_lazy_creation(monkeypatch):
    user = fake_user()
    balance = UserBalance(
        balance=90,
        monthly_spending=10,
        monthly_limit=100,
        daily_spending=10,
        daily_limit=10,
    )

    monkeypatch.setattr(auth_routes, "get_user_by_id", lambda _db, _user_id: None)
    monkeypatch.setattr(auth_routes, "create_user_profile", lambda _db, _user_id, email=None: user)
    monkeypatch.setattr(auth_routes, "calculate_user_balance", lambda *_args, **_kwargs: balance)

    response = auth_routes.get_current_user_profile({"sub": str(user.id), "email": user.email}, None)

    assert response.user == UserResponse.model_validate(user)
    assert response.balance == balance
