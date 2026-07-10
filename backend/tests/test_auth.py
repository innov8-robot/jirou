"""Tests d'intégration de l'authentification (register/login/refresh/me/rôles)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User

VALID_PASSWORD = "s3cretpwd"


def _register(client: TestClient, email: str = "alice@example.com") -> dict:
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": VALID_PASSWORD, "full_name": "Alice"},
    ).json()


def _make_user(db: Session, email: str, role: UserRole, password: str = VALID_PASSWORD) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=email.split("@")[0],
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --------------------------------------------------------------------------- #
# Register (JIR-10)
# --------------------------------------------------------------------------- #
def test_register_success(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "bob@example.com", "password": VALID_PASSWORD, "full_name": "Bob"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "bob@example.com"
    assert body["full_name"] == "Bob"
    assert body["role"] == "member"
    assert body["is_active"] is True
    assert "hashed_password" not in body
    assert "password" not in body


def test_register_duplicate_email(client: TestClient) -> None:
    _register(client, "dup@example.com")
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": VALID_PASSWORD, "full_name": "Dup"},
    )
    assert resp.status_code == 409, resp.text


def test_register_password_too_short(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "123", "full_name": "Short"},
    )
    assert resp.status_code == 422, resp.text


def test_register_invalid_email(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": VALID_PASSWORD, "full_name": "X"},
    )
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------------- #
# Login (JIR-11)
# --------------------------------------------------------------------------- #
def test_login_success(client: TestClient) -> None:
    _register(client, "login@example.com")
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": VALID_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient) -> None:
    _register(client, "wp@example.com")
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "wp@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401, resp.text


def test_login_unknown_email(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": VALID_PASSWORD},
    )
    assert resp.status_code == 401, resp.text


# --------------------------------------------------------------------------- #
# Refresh (JIR-11)
# --------------------------------------------------------------------------- #
def test_refresh_success(client: TestClient) -> None:
    _register(client, "refresh@example.com")
    tokens = client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@example.com", "password": VALID_PASSWORD},
    ).json()
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


def test_refresh_invalid_token(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "not.a.valid.token"})
    assert resp.status_code == 401, resp.text


def test_refresh_rejects_access_token(client: TestClient) -> None:
    """Un access token ne doit pas être accepté comme refresh token."""
    _register(client, "mix@example.com")
    tokens = client.post(
        "/api/v1/auth/login",
        json={"email": "mix@example.com", "password": VALID_PASSWORD},
    ).json()
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401, resp.text


# --------------------------------------------------------------------------- #
# Me (JIR-11)
# --------------------------------------------------------------------------- #
def test_me_success(client: TestClient) -> None:
    _register(client, "me@example.com")
    tokens = client.post(
        "/api/v1/auth/login",
        json={"email": "me@example.com", "password": VALID_PASSWORD},
    ).json()
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "me@example.com"


def test_me_without_token(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401, resp.text


def test_me_invalid_token(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage.token.value"})
    assert resp.status_code == 401, resp.text


# --------------------------------------------------------------------------- #
# require_role (JIR-12)
# --------------------------------------------------------------------------- #
def _login(client: TestClient, email: str, password: str = VALID_PASSWORD) -> str:
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]


def test_admin_check_forbidden_for_member(client: TestClient, db_session: Session) -> None:
    _make_user(db_session, "member@example.com", UserRole.MEMBER)
    token = _login(client, "member@example.com")
    resp = client.get("/api/v1/auth/admin-check", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403, resp.text


def test_admin_check_allowed_for_admin(client: TestClient, db_session: Session) -> None:
    _make_user(db_session, "admin@example.com", UserRole.ADMIN)
    token = _login(client, "admin@example.com")
    resp = client.get("/api/v1/auth/admin-check", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["scope"] == "admin"


def test_admin_check_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/admin-check")
    assert resp.status_code == 401, resp.text
