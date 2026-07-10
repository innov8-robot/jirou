"""Tests d'intégration de MES TICKETS (EPIC-10, JIR-72).

Couvre ``GET /users/me/issues`` : les tickets assignés à l'utilisateur courant
(tous projets où il est membre), et l'exclusion de ceux assignés à autrui.
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


def _make_user(client: TestClient, email: str) -> tuple[dict, str]:
    profile = _register(client, email)
    return profile, _login(client, email)


def _create_project(client: TestClient, token: str, key: str = "MINE") -> dict:
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


def _create_issue(client: TestClient, token: str, project_id: int, **fields: object) -> dict:
    payload = {"type": "task", "summary": "Do something", **fields}
    resp = client.post(f"/api/v1/projects/{project_id}/issues", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_my_issues_returns_only_mine(client: TestClient) -> None:
    owner_profile, owner_token = _make_user(client, "me@example.com")
    other_profile, _ = _make_user(client, "other@example.com")

    proj = _create_project(client, owner_token)
    _add_member(client, owner_token, proj["id"], "other@example.com", "member")

    mine = _create_issue(
        client, owner_token, proj["id"], summary="Pour moi", assignee_id=owner_profile["id"]
    )
    theirs = _create_issue(
        client, owner_token, proj["id"], summary="Pour l'autre", assignee_id=other_profile["id"]
    )
    _create_issue(client, owner_token, proj["id"], summary="Non assigné")

    resp = client.get("/api/v1/users/me/issues", headers=_auth(owner_token))
    assert resp.status_code == 200, resp.text
    keys = [i["key"] for i in resp.json()]
    assert mine["key"] in keys
    assert theirs["key"] not in keys
    assert all(i["assignee_id"] == owner_profile["id"] for i in resp.json())


def test_my_issues_empty_when_none_assigned(client: TestClient) -> None:
    _profile, token = _make_user(client, "nobody@example.com")
    proj = _create_project(client, token, key="NONE")
    _create_issue(client, token, proj["id"], summary="Sans assigné")

    resp = client.get("/api/v1/users/me/issues", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []
