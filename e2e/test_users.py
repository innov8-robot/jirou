"""Endpoints utilisateurs (JIR-15) — parcours accessibles sans privilège admin.

Les chemins ADMIN en succès (GET /users, PATCH /users/{id}) nécessitent un
compte admin, non créable via l'API publique (register crée un `member`) ;
ils sont couverts par la suite d'intégration backend (tests/test_users.py).
Ici on vérifie le self-service et les refus 403 côté member.
"""

from __future__ import annotations

import httpx


def test_update_own_profile(api: httpx.Client, new_user: dict) -> None:
    r = api.patch(
        "/users/me",
        headers=new_user["auth_header"],
        json={"full_name": "Nom Modifié"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "Nom Modifié"
    # /me reflète le changement.
    me = api.get("/auth/me", headers=new_user["auth_header"])
    assert me.json()["full_name"] == "Nom Modifié"


def test_change_password_then_relogin(api: httpx.Client, new_user: dict) -> None:
    r = api.put(
        "/users/me/password",
        headers=new_user["auth_header"],
        json={
            "current_password": new_user["password"],
            "new_password": "newpassword456",
        },
    )
    assert r.status_code in (200, 204), r.text

    # Nouveau mot de passe accepté...
    ok = api.post(
        "/auth/login",
        json={"email": new_user["email"], "password": "newpassword456"},
    )
    assert ok.status_code == 200
    # ...et l'ancien refusé.
    ko = api.post(
        "/auth/login",
        json={"email": new_user["email"], "password": new_user["password"]},
    )
    assert ko.status_code == 401


def test_change_password_wrong_current(api: httpx.Client, new_user: dict) -> None:
    r = api.put(
        "/users/me/password",
        headers=new_user["auth_header"],
        json={"current_password": "WRONG", "new_password": "whatever12345"},
    )
    assert r.status_code in (400, 403)


def test_list_users_forbidden_for_member(api: httpx.Client, new_user: dict) -> None:
    r = api.get("/users", headers=new_user["auth_header"])
    assert r.status_code == 403


def test_admin_update_forbidden_for_member(api: httpx.Client, new_user: dict) -> None:
    r = api.patch(
        "/users/999999",
        headers=new_user["auth_header"],
        json={"role": "admin"},
    )
    assert r.status_code == 403
