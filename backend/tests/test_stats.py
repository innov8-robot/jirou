"""Tests d'intégration du TABLEAU DE BORD projet (EPIC-10, JIR-71).

Couvre les comptages par statut/type, la liste des tickets récents et
l'avancement du sprint actif de ``GET /projects/{id}/stats``.
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


def _create_project(client: TestClient, token: str, key: str = "STAT") -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"name": f"Project {key}", "key": key},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_issue(client: TestClient, token: str, project_id: int, **fields: object) -> dict:
    payload = {"type": "task", "summary": "Do something", **fields}
    resp = client.post(f"/api/v1/projects/{project_id}/issues", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _set_status(client: TestClient, token: str, key: str, status: str) -> None:
    resp = client.patch(f"/api/v1/issues/{key}", json={"status": status}, headers=_auth(token))
    assert resp.status_code == 200, resp.text


def test_stats_counts_by_status_and_type(client: TestClient) -> None:
    token = _make_user(client, "dash@example.com")
    proj = _create_project(client, token)

    i1 = _create_issue(client, token, proj["id"], type="bug", summary="A")
    _create_issue(client, token, proj["id"], type="story", summary="B")
    _create_issue(client, token, proj["id"], type="task", summary="C")
    _set_status(client, token, i1["key"], "done")

    resp = client.get(f"/api/v1/projects/{proj['id']}/stats", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["total"] == 3
    assert body["by_status"]["todo"] == 2
    assert body["by_status"]["done"] == 1
    assert body["by_type"]["bug"] == 1
    assert body["by_type"]["story"] == 1
    assert body["by_type"]["task"] == 1
    assert body["by_type"]["epic"] == 0
    # Tickets récents (5 max), non vides ici.
    assert 1 <= len(body["recent"]) <= 5
    assert body["active_sprint"] is None


def test_stats_active_sprint_populated(client: TestClient) -> None:
    token = _make_user(client, "sprintdash@example.com")
    proj = _create_project(client, token)

    issue = _create_issue(client, token, proj["id"], summary="In sprint", story_points=5)

    # Crée + démarre un sprint, puis y place l'issue.
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/sprints",
        json={"name": "Sprint 1"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    sprint_id = resp.json()["id"]

    resp = client.post(f"/api/v1/sprints/{sprint_id}/start", json={}, headers=_auth(token))
    assert resp.status_code == 200, resp.text

    resp = client.patch(
        f"/api/v1/issues/{issue['key']}/backlog-move",
        json={"sprint_id": sprint_id, "position": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    _set_status(client, token, issue["key"], "done")

    resp = client.get(f"/api/v1/projects/{proj['id']}/stats", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    active = resp.json()["active_sprint"]
    assert active is not None
    assert active["sprint"]["id"] == sprint_id
    assert active["total"] == 1
    assert active["done"] == 1
    assert active["points_total"] == 5
    assert active["points_done"] == 5
