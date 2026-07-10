"""Tests d'intégration des NOTIFICATIONS in-app (EPIC-09, JIR-67).

Couvre la création sur mention et sur changement d'assigné (destinataire = le
nouvel assigné, pas l'acteur), le compteur de non-lues, le marquage lu et
« tout marquer lu », et l'isolation (chacun ne voit que ses notifications).
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


def _add_member(client: TestClient, token: str, project_id: int, email: str, role: str) -> None:
    resp = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": email, "role": role},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text


def _create_issue(client: TestClient, token: str, project_id: int, **fields: object) -> dict:
    payload = {"type": "task", "summary": "Do something", **fields}
    resp = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json=payload,
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _patch_issue(client: TestClient, token: str, key: str, **fields: object) -> object:
    return client.patch(f"/api/v1/issues/{key}", json=fields, headers=_auth(token))


def _notifs(client: TestClient, token: str, **params: object) -> list[dict]:
    resp = client.get("/api/v1/notifications", params=params, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _unread(client: TestClient, token: str) -> int:
    resp = client.get("/api/v1/notifications/unread-count", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["count"]


# --------------------------------------------------------------------------- #
# Assignation
# --------------------------------------------------------------------------- #
def test_assignment_creates_notification_for_new_assignee(client: TestClient) -> None:
    lead_profile, lead_token = _make_user(client, "manager@example.com", "Manager")
    assignee_profile, _ = _make_user(client, "dev@example.com", "Dev")
    proj = _create_project(client, lead_token, key="ASG")
    _add_member(client, lead_token, proj["id"], "dev@example.com", "member")
    issue = _create_issue(client, lead_token, proj["id"])

    resp = _patch_issue(client, lead_token, issue["key"], assignee_id=assignee_profile["id"])
    assert resp.status_code == 200, resp.text

    assignee_token = _login(client, "dev@example.com")
    notifs = _notifs(client, assignee_token)
    assert len(notifs) == 1
    assert notifs[0]["type"] == "assignment"
    assert notifs[0]["actor"]["id"] == lead_profile["id"]
    assert notifs[0]["issue_key"] == issue["key"]
    assert notifs[0]["project_id"] == proj["id"]

    # L'acteur (le lead) n'est pas notifié.
    assert _unread(client, lead_token) == 0


def test_self_assignment_creates_no_notification(client: TestClient) -> None:
    lead_profile, lead_token = _make_user(client, "solo@example.com")
    proj = _create_project(client, lead_token, key="SLF")
    issue = _create_issue(client, lead_token, proj["id"])

    resp = _patch_issue(client, lead_token, issue["key"], assignee_id=lead_profile["id"])
    assert resp.status_code == 200, resp.text
    assert _unread(client, lead_token) == 0


def test_unchanged_assignee_creates_no_new_notification(client: TestClient) -> None:
    _, lead_token = _make_user(client, "mgr2@example.com")
    assignee_profile, _ = _make_user(client, "dev2@example.com")
    proj = _create_project(client, lead_token, key="UNC")
    _add_member(client, lead_token, proj["id"], "dev2@example.com", "member")
    issue = _create_issue(client, lead_token, proj["id"])

    assignee_token = _login(client, "dev2@example.com")
    # Première assignation : une notification.
    _patch_issue(client, lead_token, issue["key"], assignee_id=assignee_profile["id"])
    assert _unread(client, assignee_token) == 1

    # Ré-assigner le même utilisateur (assigné inchangé) ne crée pas de doublon.
    _patch_issue(client, lead_token, issue["key"], assignee_id=assignee_profile["id"])
    assert _unread(client, assignee_token) == 1


# --------------------------------------------------------------------------- #
# Compteur / marquage
# --------------------------------------------------------------------------- #
def test_mark_read_and_read_all(client: TestClient) -> None:
    _, lead_token = _make_user(client, "boss3@example.com")
    dev_profile, _ = _make_user(client, "dev3@example.com")
    proj = _create_project(client, lead_token, key="RD")
    _add_member(client, lead_token, proj["id"], "dev3@example.com", "member")

    i1 = _create_issue(client, lead_token, proj["id"])
    i2 = _create_issue(client, lead_token, proj["id"])
    _patch_issue(client, lead_token, i1["key"], assignee_id=dev_profile["id"])
    _patch_issue(client, lead_token, i2["key"], assignee_id=dev_profile["id"])

    dev_token = _login(client, "dev3@example.com")
    assert _unread(client, dev_token) == 2

    notifs = _notifs(client, dev_token)
    first_id = notifs[0]["id"]
    marked = client.patch(f"/api/v1/notifications/{first_id}/read", headers=_auth(dev_token))
    assert marked.status_code == 200, marked.text
    assert marked.json()["is_read"] is True
    assert _unread(client, dev_token) == 1

    # unread_only ne renvoie que les non-lues.
    assert all(n["is_read"] is False for n in _notifs(client, dev_token, unread_only=True))
    assert len(_notifs(client, dev_token, unread_only=True)) == 1

    read_all = client.post("/api/v1/notifications/read-all", headers=_auth(dev_token))
    assert read_all.status_code == 200, read_all.text
    assert read_all.json()["updated"] == 1
    assert _unread(client, dev_token) == 0


def test_cannot_mark_others_notification(client: TestClient) -> None:
    _, lead_token = _make_user(client, "boss4@example.com")
    dev_profile, _ = _make_user(client, "dev4@example.com")
    _make_user(client, "intruder@example.com")
    proj = _create_project(client, lead_token, key="OWN")
    _add_member(client, lead_token, proj["id"], "dev4@example.com", "member")
    issue = _create_issue(client, lead_token, proj["id"])
    _patch_issue(client, lead_token, issue["key"], assignee_id=dev_profile["id"])

    dev_token = _login(client, "dev4@example.com")
    notif_id = _notifs(client, dev_token)[0]["id"]

    intruder_token = _login(client, "intruder@example.com")
    resp = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=_auth(intruder_token))
    assert resp.status_code == 404, resp.text


def test_user_only_sees_own_notifications(client: TestClient) -> None:
    _, lead_token = _make_user(client, "boss5@example.com")
    dev_profile, _ = _make_user(client, "dev5@example.com")
    _make_user(client, "bystander5@example.com")
    proj = _create_project(client, lead_token, key="ISO")
    _add_member(client, lead_token, proj["id"], "dev5@example.com", "member")
    _add_member(client, lead_token, proj["id"], "bystander5@example.com", "member")
    issue = _create_issue(client, lead_token, proj["id"])
    _patch_issue(client, lead_token, issue["key"], assignee_id=dev_profile["id"])

    bystander_token = _login(client, "bystander5@example.com")
    assert _notifs(client, bystander_token) == []
    assert _unread(client, bystander_token) == 0
