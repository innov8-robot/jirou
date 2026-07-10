"""Tests d'intégration des VUES SAUVEGARDÉES (EPIC-10, JIR-70).

Couvre create/list/delete, le conflit 409 sur nom dupliqué, l'isolation par
utilisateur et le 403 lors de la suppression de la vue d'autrui.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

VALID_PASSWORD = "s3cretpwd"


def _register(client: TestClient, email: str, full_name: str = "User") -> dict:
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": VALID_PASSWORD, "full_name": full_name},
    ).json()


def _login(client: TestClient, email: str) -> str:
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": VALID_PASSWORD},
    ).json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(client: TestClient, email: str) -> str:
    _register(client, email)
    return _login(client, email)


def _create_project(client: TestClient, token: str, key: str = "VIEW") -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"name": f"Project {key}", "key": key},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _add_member(client: TestClient, token: str, project_id: int, email: str, role: str) -> None:
    resp = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": email, "role": role},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text


def _create_view(client: TestClient, token: str, project_id: int, name: str, filters: dict):
    return client.post(
        f"/api/v1/projects/{project_id}/views",
        json={"name": name, "filters": filters},
        headers=_auth(token),
    )


def test_create_list_delete_view(client: TestClient) -> None:
    token = _make_user(client, "viewowner@example.com")
    proj = _create_project(client, token)

    filters = {"status": ["todo", "in_progress"], "assignee_id": 1}
    resp = _create_view(client, token, proj["id"], "Mes urgents", filters)
    assert resp.status_code == 201, resp.text
    view = resp.json()
    assert view["name"] == "Mes urgents"
    assert view["filters"] == filters
    assert view["project_id"] == proj["id"]

    # Liste.
    resp = client.get(f"/api/v1/projects/{proj['id']}/views", headers=_auth(token))
    assert resp.status_code == 200
    assert [v["id"] for v in resp.json()] == [view["id"]]

    # Suppression.
    resp = client.delete(f"/api/v1/views/{view['id']}", headers=_auth(token))
    assert resp.status_code == 204

    resp = client.get(f"/api/v1/projects/{proj['id']}/views", headers=_auth(token))
    assert resp.json() == []


def test_duplicate_name_conflicts(client: TestClient) -> None:
    token = _make_user(client, "dup@example.com")
    proj = _create_project(client, token, key="DUP")

    assert _create_view(client, token, proj["id"], "Sprint courant", {}).status_code == 201
    resp = _create_view(client, token, proj["id"], "Sprint courant", {"type": ["bug"]})
    assert resp.status_code == 409, resp.text


def test_views_isolated_by_user(client: TestClient) -> None:
    owner_token = _make_user(client, "a@example.com")
    member_token = _make_user(client, "b@example.com")
    proj = _create_project(client, owner_token, key="ISO")
    _add_member(client, owner_token, proj["id"], "b@example.com", "member")

    _create_view(client, owner_token, proj["id"], "Vue de A", {})
    _create_view(client, member_token, proj["id"], "Vue de B", {})

    # Chacun ne voit que sa propre vue.
    resp = client.get(f"/api/v1/projects/{proj['id']}/views", headers=_auth(owner_token))
    assert [v["name"] for v in resp.json()] == ["Vue de A"]

    resp = client.get(f"/api/v1/projects/{proj['id']}/views", headers=_auth(member_token))
    assert [v["name"] for v in resp.json()] == ["Vue de B"]


def test_delete_others_view_forbidden(client: TestClient) -> None:
    owner_token = _make_user(client, "owner2@example.com")
    intruder_token = _make_user(client, "intruder@example.com")
    proj = _create_project(client, owner_token, key="FORB")
    _add_member(client, owner_token, proj["id"], "intruder@example.com", "member")

    view = _create_view(client, owner_token, proj["id"], "Privée", {}).json()

    resp = client.delete(f"/api/v1/views/{view['id']}", headers=_auth(intruder_token))
    assert resp.status_code == 403, resp.text

    # Introuvable -> 404.
    resp = client.delete("/api/v1/views/999999", headers=_auth(intruder_token))
    assert resp.status_code == 404
