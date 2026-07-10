"""Tests d'intégration de la TIMELINE (EPIC-08, JIR-56).

Couvre : liste des epics avec enfants et progression correcte, epic sans dates
renvoyé quand même, accès interdit au non-membre (403), et présence des
dépendances epic↔epic dans ``dependencies``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

VALID_PASSWORD = "s3cretpwd"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
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


def _make_user(client: TestClient, email: str, full_name: str = "User") -> tuple[dict, str]:
    profile = _register(client, email, full_name)
    return profile, _login(client, email)


def _create_project(client: TestClient, token: str, key: str = "DEMO") -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"name": f"Project {key}", "key": key},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_issue(client: TestClient, token: str, project_id: int, **fields: object) -> dict:
    payload = {"type": "task", "summary": "Do something", **fields}
    resp = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json=payload,
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _patch_issue(client: TestClient, token: str, key: str, **fields: object) -> dict:
    resp = client.patch(
        f"/api/v1/issues/{key}",
        json=fields,
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _create_dep(client: TestClient, token: str, from_key: str, target_key: str) -> None:
    resp = client.post(
        f"/api/v1/issues/{from_key}/dependencies",
        json={"target_key": target_key},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text


def _timeline(client: TestClient, token: str, project_id: int):
    return client.get(f"/api/v1/projects/{project_id}/timeline", headers=_auth(token))


# --------------------------------------------------------------------------- #
# GET /projects/{id}/timeline
# --------------------------------------------------------------------------- #
def test_timeline_epics_with_children_and_progress(client: TestClient) -> None:
    _, token = _make_user(client, "tl1@example.com")
    proj = _create_project(client, token, key="TLA")
    epic = _create_issue(
        client, token, proj["id"], type="epic", summary="Epic 1", start_date="2026-01-01"
    )
    c1 = _create_issue(client, token, proj["id"], summary="Child 1", epic_id=epic["id"])
    _create_issue(client, token, proj["id"], summary="Child 2", epic_id=epic["id"])
    _create_issue(client, token, proj["id"], summary="Child 3", epic_id=epic["id"])
    # Un enfant terminé.
    _patch_issue(client, token, c1["key"], status="done")

    resp = _timeline(client, token, proj["id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["epics"]) == 1
    entry = body["epics"][0]
    assert entry["epic"]["key"] == epic["key"]
    assert entry["epic"]["type"] == "epic"
    assert len(entry["children"]) == 3
    assert entry["progress"] == {"done": 1, "total": 3}
    assert body["dependencies"] == []


def test_timeline_epic_without_dates_returned(client: TestClient) -> None:
    _, token = _make_user(client, "tl2@example.com")
    proj = _create_project(client, token, key="TLB")
    epic = _create_issue(client, token, proj["id"], type="epic", summary="No dates")

    resp = _timeline(client, token, proj["id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["epics"]) == 1
    entry = body["epics"][0]
    assert entry["epic"]["key"] == epic["key"]
    assert entry["epic"]["start_date"] is None
    assert entry["epic"]["due_date"] is None
    assert entry["children"] == []
    assert entry["progress"] == {"done": 0, "total": 0}


def test_timeline_non_member_forbidden(client: TestClient) -> None:
    _, owner_token = _make_user(client, "tlowner@example.com")
    _, outsider_token = _make_user(client, "tloutsider@example.com")
    proj = _create_project(client, owner_token, key="TLC")

    resp = _timeline(client, outsider_token, proj["id"])
    assert resp.status_code == 403, resp.text


def test_timeline_unknown_project_404(client: TestClient) -> None:
    _, token = _make_user(client, "tl404@example.com")
    resp = _timeline(client, token, 999999)
    assert resp.status_code == 404, resp.text


def test_timeline_epic_dependencies_listed(client: TestClient) -> None:
    _, token = _make_user(client, "tl3@example.com")
    proj = _create_project(client, token, key="TLD")
    epic_a = _create_issue(client, token, proj["id"], type="epic", summary="Epic A")
    epic_b = _create_issue(client, token, proj["id"], type="epic", summary="Epic B")
    # Une dépendance entre deux non-epics ne doit PAS apparaître.
    task_a = _create_issue(client, token, proj["id"], summary="Task A")
    task_b = _create_issue(client, token, proj["id"], summary="Task B")

    _create_dep(client, token, epic_a["key"], epic_b["key"])
    _create_dep(client, token, task_a["key"], task_b["key"])

    resp = _timeline(client, token, proj["id"])
    assert resp.status_code == 200, resp.text
    deps = resp.json()["dependencies"]
    assert deps == [{"from_key": epic_a["key"], "to_key": epic_b["key"]}]
