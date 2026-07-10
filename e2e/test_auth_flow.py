"""Parcours d'authentification complet contre l'API réelle (EPIC-02)."""

from __future__ import annotations

import httpx

from conftest import unique_email


def test_register_success(api: httpx.Client) -> None:
    email = unique_email()
    r = api.post(
        "/auth/register",
        json={"email": email, "password": "password123", "full_name": "Alice"},
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body["email"] == email
    assert body["role"] == "member"
    assert "hashed_password" not in body
    assert "password" not in body


def test_register_duplicate_conflict(api: httpx.Client) -> None:
    email = unique_email()
    payload = {"email": email, "password": "password123", "full_name": "Dup"}
    assert api.post("/auth/register", json=payload).status_code in (200, 201)
    assert api.post("/auth/register", json=payload).status_code == 409


def test_register_weak_password_rejected(api: httpx.Client) -> None:
    r = api.post(
        "/auth/register",
        json={"email": unique_email(), "password": "short", "full_name": "Weak"},
    )
    assert r.status_code == 422


def test_login_returns_tokens(new_user: dict) -> None:
    assert new_user["access_token"]
    assert new_user["refresh_token"]


def test_login_wrong_password(api: httpx.Client, new_user: dict) -> None:
    r = api.post(
        "/auth/login",
        json={"email": new_user["email"], "password": "WRONG_PASSWORD"},
    )
    assert r.status_code == 401


def test_login_unknown_email(api: httpx.Client) -> None:
    r = api.post(
        "/auth/login",
        json={"email": unique_email(), "password": "password123"},
    )
    assert r.status_code == 401


def test_me_with_token(api: httpx.Client, new_user: dict) -> None:
    r = api.get("/auth/me", headers=new_user["auth_header"])
    assert r.status_code == 200
    assert r.json()["email"] == new_user["email"]


def test_me_without_token(api: httpx.Client) -> None:
    assert api.get("/auth/me").status_code == 401


def test_me_invalid_token(api: httpx.Client) -> None:
    r = api.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_refresh_returns_new_access_token(api: httpx.Client, new_user: dict) -> None:
    r = api.post("/auth/refresh", json={"refresh_token": new_user["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_member_forbidden_on_admin_route(api: httpx.Client, new_user: dict) -> None:
    r = api.get("/auth/admin-check", headers=new_user["auth_header"])
    assert r.status_code == 403
