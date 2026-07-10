"""Tests d'intégration de la gestion des utilisateurs (JIR-15).

Couvre le profil personnel (PATCH /users/me, PUT /users/me/password) et
l'administration des comptes (GET /users, PATCH /users/{id}).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User

VALID_PASSWORD = "s3cretpwd"


def _register(client: TestClient, email: str, full_name: str = "User") -> dict:
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": VALID_PASSWORD, "full_name": full_name},
    ).json()


def _login(client: TestClient, email: str, password: str = VALID_PASSWORD) -> str:
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# PATCH /users/me
# --------------------------------------------------------------------------- #
def test_update_me_success(client: TestClient) -> None:
    _register(client, "profile@example.com", "Old Name")
    token = _login(client, "profile@example.com")
    resp = client.patch(
        "/api/v1/users/me",
        json={"full_name": "New Name", "avatar_url": "https://cdn/x.png"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["full_name"] == "New Name"
    assert body["avatar_url"] == "https://cdn/x.png"
    assert body["email"] == "profile@example.com"


def test_update_me_partial_keeps_other_fields(client: TestClient) -> None:
    _register(client, "partial@example.com", "Keep Name")
    token = _login(client, "partial@example.com")
    resp = client.patch(
        "/api/v1/users/me",
        json={"avatar_url": "https://cdn/y.png"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["full_name"] == "Keep Name"
    assert body["avatar_url"] == "https://cdn/y.png"


def test_update_me_does_not_affect_others(client: TestClient) -> None:
    _register(client, "one@example.com", "One")
    _register(client, "two@example.com", "Two")
    token_one = _login(client, "one@example.com")

    client.patch(
        "/api/v1/users/me",
        json={"full_name": "One Renamed"},
        headers=_auth(token_one),
    )

    token_two = _login(client, "two@example.com")
    me_two = client.get("/api/v1/auth/me", headers=_auth(token_two)).json()
    assert me_two["full_name"] == "Two"


def test_update_me_requires_auth(client: TestClient) -> None:
    resp = client.patch("/api/v1/users/me", json={"full_name": "X"})
    assert resp.status_code == 401, resp.text


# --------------------------------------------------------------------------- #
# PUT /users/me/password
# --------------------------------------------------------------------------- #
def test_change_password_success_then_login(client: TestClient) -> None:
    _register(client, "pwd@example.com")
    token = _login(client, "pwd@example.com")
    new_password = "brandNewPwd9"
    resp = client.put(
        "/api/v1/users/me/password",
        json={"current_password": VALID_PASSWORD, "new_password": new_password},
        headers=_auth(token),
    )
    assert resp.status_code == 204, resp.text

    # L'ancien mot de passe ne fonctionne plus, le nouveau oui.
    old = client.post(
        "/api/v1/auth/login",
        json={"email": "pwd@example.com", "password": VALID_PASSWORD},
    )
    assert old.status_code == 401, old.text
    new = client.post(
        "/api/v1/auth/login",
        json={"email": "pwd@example.com", "password": new_password},
    )
    assert new.status_code == 200, new.text


def test_change_password_wrong_current(client: TestClient) -> None:
    _register(client, "wrongpwd@example.com")
    token = _login(client, "wrongpwd@example.com")
    resp = client.put(
        "/api/v1/users/me/password",
        json={"current_password": "not-the-password", "new_password": "anotherPwd9"},
        headers=_auth(token),
    )
    assert resp.status_code == 400, resp.text


def test_change_password_too_short(client: TestClient) -> None:
    _register(client, "shortpwd@example.com")
    token = _login(client, "shortpwd@example.com")
    resp = client.put(
        "/api/v1/users/me/password",
        json={"current_password": VALID_PASSWORD, "new_password": "123"},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------------- #
# GET /users (admin uniquement)
# --------------------------------------------------------------------------- #
def test_list_users_as_admin(client: TestClient, admin_token: str) -> None:
    _register(client, "listed@example.com")
    resp = client.get("/api/v1/users", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    emails = {u["email"] for u in body}
    assert "listed@example.com" in emails


def test_list_users_pagination(client: TestClient, admin_token: str) -> None:
    _register(client, "p1@example.com")
    _register(client, "p2@example.com")
    resp = client.get("/api/v1/users?skip=0&limit=1", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1


def test_list_users_forbidden_for_member(client: TestClient) -> None:
    _register(client, "notadmin@example.com")
    token = _login(client, "notadmin@example.com")
    resp = client.get("/api/v1/users", headers=_auth(token))
    assert resp.status_code == 403, resp.text


def test_list_users_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/users")
    assert resp.status_code == 401, resp.text


# --------------------------------------------------------------------------- #
# PATCH /users/{user_id} (admin uniquement)
# --------------------------------------------------------------------------- #
def _seed_member(db_session: Session, email: str) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(VALID_PASSWORD),
        full_name=email.split("@")[0],
        role=UserRole.MEMBER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_admin_update_role(client: TestClient, admin_token: str, db_session: Session) -> None:
    target = _seed_member(db_session, "promote@example.com")
    resp = client.patch(
        f"/api/v1/users/{target.id}",
        json={"role": "admin"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == "admin"
    assert body["id"] == target.id


def test_admin_update_deactivate(client: TestClient, admin_token: str, db_session: Session) -> None:
    target = _seed_member(db_session, "deact@example.com")
    resp = client.patch(
        f"/api/v1/users/{target.id}",
        json={"is_active": False},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is False


def test_admin_update_self_demotion_blocked(
    client: TestClient, admin_token: str, admin_user: User
) -> None:
    resp = client.patch(
        f"/api/v1/users/{admin_user.id}",
        json={"role": "member"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400, resp.text


def test_admin_update_self_deactivate_blocked(
    client: TestClient, admin_token: str, admin_user: User
) -> None:
    resp = client.patch(
        f"/api/v1/users/{admin_user.id}",
        json={"is_active": False},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400, resp.text


def test_admin_update_unknown_user(client: TestClient, admin_token: str) -> None:
    resp = client.patch(
        "/api/v1/users/999999",
        json={"role": "viewer"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404, resp.text


def test_admin_update_forbidden_for_member(client: TestClient, db_session: Session) -> None:
    _seed_member(db_session, "actor@example.com")
    target = _seed_member(db_session, "victim@example.com")
    token = _login(client, "actor@example.com")
    resp = client.patch(
        f"/api/v1/users/{target.id}",
        json={"role": "admin"},
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text
