"""Tests d'intégration du JOURNAL D'ACTIVITÉ (EPIC-10, JIR-69).

Couvre l'écriture automatique d'entrées à la création d'un ticket, sur les
changements de champ (statut) et à la publication d'un commentaire, ainsi que
l'ordre chronologique inverse (récentes d'abord) de ``GET /issues/{key}/activity``.
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


def _create_project(client: TestClient, token: str, key: str = "ACT") -> dict:
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


def _activity(client: TestClient, token: str, key: str) -> list[dict]:
    resp = client.get(f"/api/v1/issues/{key}/activity", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_creation_logs_created_entry(client: TestClient) -> None:
    token = _make_user(client, "creator@example.com")
    proj = _create_project(client, token)
    issue = _create_issue(client, token, proj["id"])

    entries = _activity(client, token, issue["key"])
    assert len(entries) == 1
    assert entries[0]["action"] == "created"
    assert entries[0]["actor"] is not None
    assert entries[0]["actor"]["email"] == "creator@example.com"


def test_status_change_logs_updated_entry(client: TestClient) -> None:
    token = _make_user(client, "mover@example.com")
    proj = _create_project(client, token)
    issue = _create_issue(client, token, proj["id"])

    resp = client.patch(
        f"/api/v1/issues/{issue['key']}",
        json={"status": "in_progress"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    entries = _activity(client, token, issue["key"])
    updated = [e for e in entries if e["action"] == "updated"]
    assert len(updated) == 1
    assert updated[0]["field"] == "status"
    assert updated[0]["old_value"] == "todo"
    assert updated[0]["new_value"] == "in_progress"


def test_comment_logs_commented_entry(client: TestClient) -> None:
    token = _make_user(client, "commenter@example.com")
    proj = _create_project(client, token)
    issue = _create_issue(client, token, proj["id"])

    resp = client.post(
        f"/api/v1/issues/{issue['key']}/comments",
        json={"body": "Un commentaire"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text

    entries = _activity(client, token, issue["key"])
    actions = [e["action"] for e in entries]
    assert "commented" in actions


def test_activity_ordered_recent_first(client: TestClient) -> None:
    token = _make_user(client, "ordered@example.com")
    proj = _create_project(client, token)
    issue = _create_issue(client, token, proj["id"])

    client.patch(
        f"/api/v1/issues/{issue['key']}",
        json={"status": "in_progress"},
        headers=_auth(token),
    )
    client.post(
        f"/api/v1/issues/{issue['key']}/comments",
        json={"body": "plus tard"},
        headers=_auth(token),
    )

    entries = _activity(client, token, issue["key"])
    # created (le plus ancien) doit apparaître en dernier ; les ids décroissent.
    assert entries[-1]["action"] == "created"
    ids = [e["id"] for e in entries]
    assert ids == sorted(ids, reverse=True)
