"""Tests d'intégration du domaine TICKETS (EPIC-05, JIR-30 à JIR-35).

Réutilise les fixtures de ``conftest`` (client, db_session, admin_token) ainsi
que le flux d'inscription/connexion standard. Couvre la création (clé auto,
reporter, défauts, permissions), la lecture/liste filtrée, la mise à jour, la
suppression et la hiérarchie Epic <-> enfants.
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


# --------------------------------------------------------------------------- #
# POST /projects/{id}/issues
# --------------------------------------------------------------------------- #
def test_create_issue_defaults_and_key(client: TestClient) -> None:
    profile, token = _make_user(client, "creator@example.com", "Creator")
    proj = _create_project(client, token, key="JIR")
    body = _create_issue(client, token, proj["id"], summary="First")

    assert body["key"] == "JIR-1"
    assert body["status"] == "todo"
    assert body["priority"] == "medium"
    assert body["reporter_id"] == profile["id"]
    assert body["reporter"]["email"] == "creator@example.com"
    assert body["assignee"] is None
    assert body["labels"] == []
    assert body["position"] == 0


def test_create_issue_keys_sequential_per_project(client: TestClient) -> None:
    _, token = _make_user(client, "seq@example.com")
    proj_a = _create_project(client, token, key="AAA")
    proj_b = _create_project(client, token, key="BBB")

    a1 = _create_issue(client, token, proj_a["id"])
    a2 = _create_issue(client, token, proj_a["id"])
    b1 = _create_issue(client, token, proj_b["id"])

    assert a1["key"] == "AAA-1"
    assert a2["key"] == "AAA-2"
    # Compteur indépendant par projet.
    assert b1["key"] == "BBB-1"


def test_create_many_issues_distinct_keys(client: TestClient) -> None:
    _, token = _make_user(client, "many@example.com")
    proj = _create_project(client, token, key="MNY")
    keys = {_create_issue(client, token, proj["id"])["key"] for _ in range(10)}
    assert len(keys) == 10
    assert keys == {f"MNY-{n}" for n in range(1, 11)}


def test_create_issue_viewer_forbidden(client: TestClient) -> None:
    _, lead_token = _make_user(client, "boss@example.com")
    _make_user(client, "view@example.com")
    proj = _create_project(client, lead_token, key="VWR")
    _add_member(client, lead_token, proj["id"], "view@example.com", "viewer")
    viewer_token = _login(client, "view@example.com")
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/issues",
        json={"type": "task", "summary": "Nope"},
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403, resp.text


def test_create_issue_non_member_forbidden(client: TestClient) -> None:
    _, token = _make_user(client, "owner1@example.com")
    _, stranger = _make_user(client, "stranger1@example.com")
    proj = _create_project(client, token, key="NMB")
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/issues",
        json={"type": "task", "summary": "X"},
        headers=_auth(stranger),
    )
    assert resp.status_code == 403, resp.text


def test_create_issue_unknown_project_404(client: TestClient) -> None:
    _, token = _make_user(client, "np@example.com")
    resp = client.post(
        "/api/v1/projects/999999/issues",
        json={"type": "task", "summary": "X"},
        headers=_auth(token),
    )
    assert resp.status_code == 404, resp.text


def test_create_issue_with_labels_and_assignee(client: TestClient) -> None:
    profile, token = _make_user(client, "full@example.com")
    proj = _create_project(client, token, key="FUL")
    label = client.post(
        f"/api/v1/projects/{proj['id']}/labels",
        json={"name": "backend", "color": "#00ff00"},
        headers=_auth(token),
    ).json()
    body = _create_issue(
        client,
        token,
        proj["id"],
        assignee_id=profile["id"],
        label_ids=[label["id"]],
        priority="high",
        story_points=5,
    )
    assert body["assignee"]["id"] == profile["id"]
    assert body["priority"] == "high"
    assert body["story_points"] == 5
    assert [lbl["name"] for lbl in body["labels"]] == ["backend"]


def test_create_issue_assignee_not_member_422(client: TestClient) -> None:
    _, token = _make_user(client, "own@example.com")
    outsider, _ = _make_user(client, "outsider@example.com")
    proj = _create_project(client, token, key="ASG")
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/issues",
        json={"type": "task", "summary": "X", "assignee_id": outsider["id"]},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text


def test_create_issue_label_other_project_422(client: TestClient) -> None:
    _, token = _make_user(client, "lbl@example.com")
    proj_a = _create_project(client, token, key="LPA")
    proj_b = _create_project(client, token, key="LPB")
    label_b = client.post(
        f"/api/v1/projects/{proj_b['id']}/labels",
        json={"name": "shared", "color": "#123456"},
        headers=_auth(token),
    ).json()
    resp = client.post(
        f"/api/v1/projects/{proj_a['id']}/issues",
        json={"type": "task", "summary": "X", "label_ids": [label_b["id"]]},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------------- #
# GET /projects/{id}/issues (liste + filtres + tri)
# --------------------------------------------------------------------------- #
def test_list_issues_and_filters(client: TestClient) -> None:
    profile, token = _make_user(client, "list@example.com")
    proj = _create_project(client, token, key="LST")

    bug = _create_issue(client, token, proj["id"], type="bug", summary="crash on save")
    story = _create_issue(
        client, token, proj["id"], type="story", summary="new feature", assignee_id=profile["id"]
    )
    label = client.post(
        f"/api/v1/projects/{proj['id']}/labels",
        json={"name": "urgent", "color": "#ff0000"},
        headers=_auth(token),
    ).json()
    client.patch(
        f"/api/v1/issues/{story['key']}",
        json={"status": "done", "label_ids": [label["id"]]},
        headers=_auth(token),
    )

    def _list(query: str = "") -> list[dict]:
        resp = client.get(f"/api/v1/projects/{proj['id']}/issues{query}", headers=_auth(token))
        assert resp.status_code == 200, resp.text
        return resp.json()

    assert len(_list()) == 2
    assert [i["key"] for i in _list("?type=bug")] == [bug["key"]]
    assert [i["key"] for i in _list("?status=done")] == [story["key"]]
    assert [i["key"] for i in _list(f"?assignee_id={profile['id']}")] == [story["key"]]
    assert [i["key"] for i in _list(f"?label_id={label['id']}")] == [story["key"]]
    assert [i["key"] for i in _list("?search=crash")] == [bug["key"]]

    # Tri décroissant par clé -> story (LST-2) avant bug (LST-1).
    sorted_desc = _list("?sort=-key")
    assert [i["key"] for i in sorted_desc] == [story["key"], bug["key"]]


def test_list_issues_filter_epic(client: TestClient) -> None:
    _, token = _make_user(client, "epicf@example.com")
    proj = _create_project(client, token, key="EPF")
    epic = _create_issue(client, token, proj["id"], type="epic", summary="Big epic")
    child = _create_issue(client, token, proj["id"], type="story", epic_id=epic["id"])
    _create_issue(client, token, proj["id"], type="task", summary="unrelated")

    resp = client.get(
        f"/api/v1/projects/{proj['id']}/issues?epic_id={epic['id']}", headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text
    assert [i["key"] for i in resp.json()] == [child["key"]]


def test_list_issues_non_member_forbidden(client: TestClient) -> None:
    _, token = _make_user(client, "owner2@example.com")
    _, stranger = _make_user(client, "stranger2@example.com")
    proj = _create_project(client, token, key="LNM")
    resp = client.get(f"/api/v1/projects/{proj['id']}/issues", headers=_auth(stranger))
    assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------------- #
# GET /issues/{key}
# --------------------------------------------------------------------------- #
def test_get_issue_by_key_member_ok(client: TestClient) -> None:
    _, token = _make_user(client, "getk@example.com")
    proj = _create_project(client, token, key="GTK")
    issue = _create_issue(client, token, proj["id"], description="<p>hello</p>")
    resp = client.get(f"/api/v1/issues/{issue['key']}", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"] == issue["key"]
    assert body["description"] == "<p>hello</p>"
    assert body["children"] == []
    assert body["progress"] is None


def test_get_issue_non_member_forbidden(client: TestClient) -> None:
    _, token = _make_user(client, "owner3@example.com")
    _, stranger = _make_user(client, "stranger3@example.com")
    proj = _create_project(client, token, key="GNM")
    issue = _create_issue(client, token, proj["id"])
    resp = client.get(f"/api/v1/issues/{issue['key']}", headers=_auth(stranger))
    assert resp.status_code == 403, resp.text


def test_get_issue_unknown_key_404(client: TestClient) -> None:
    _, token = _make_user(client, "unk@example.com")
    resp = client.get("/api/v1/issues/NOPE-999", headers=_auth(token))
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------------- #
# PATCH /issues/{key}
# --------------------------------------------------------------------------- #
def test_patch_issue_fields(client: TestClient) -> None:
    profile, token = _make_user(client, "patch@example.com")
    proj = _create_project(client, token, key="PCH")
    issue = _create_issue(client, token, proj["id"])
    before = client.get(f"/api/v1/issues/{issue['key']}", headers=_auth(token)).json()

    resp = client.patch(
        f"/api/v1/issues/{issue['key']}",
        json={
            "status": "in_progress",
            "priority": "highest",
            "story_points": 8,
            "assignee_id": profile["id"],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["priority"] == "highest"
    assert body["story_points"] == 8
    assert body["assignee"]["id"] == profile["id"]
    assert body["updated_at"] >= before["updated_at"]


def test_patch_issue_labels_replace(client: TestClient) -> None:
    _, token = _make_user(client, "plbl@example.com")
    proj = _create_project(client, token, key="PLB")
    issue = _create_issue(client, token, proj["id"])
    l1 = client.post(
        f"/api/v1/projects/{proj['id']}/labels",
        json={"name": "one", "color": "#111111"},
        headers=_auth(token),
    ).json()
    l2 = client.post(
        f"/api/v1/projects/{proj['id']}/labels",
        json={"name": "two", "color": "#222222"},
        headers=_auth(token),
    ).json()

    client.patch(
        f"/api/v1/issues/{issue['key']}", json={"label_ids": [l1["id"]]}, headers=_auth(token)
    )
    client.patch(
        f"/api/v1/issues/{issue['key']}", json={"label_ids": [l2["id"]]}, headers=_auth(token)
    )
    body = client.get(f"/api/v1/issues/{issue['key']}", headers=_auth(token)).json()
    assert [lbl["name"] for lbl in body["labels"]] == ["two"]


def test_patch_issue_viewer_forbidden(client: TestClient) -> None:
    _, lead_token = _make_user(client, "pboss@example.com")
    _make_user(client, "pview@example.com")
    proj = _create_project(client, lead_token, key="PVW")
    _add_member(client, lead_token, proj["id"], "pview@example.com", "viewer")
    issue = _create_issue(client, lead_token, proj["id"])
    viewer_token = _login(client, "pview@example.com")
    resp = client.patch(
        f"/api/v1/issues/{issue['key']}", json={"summary": "hijack"}, headers=_auth(viewer_token)
    )
    assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------------- #
# DELETE /issues/{key}
# --------------------------------------------------------------------------- #
def test_delete_issue_by_reporter(client: TestClient) -> None:
    _, token = _make_user(client, "delr@example.com")
    proj = _create_project(client, token, key="DLR")
    issue = _create_issue(client, token, proj["id"])
    resp = client.delete(f"/api/v1/issues/{issue['key']}", headers=_auth(token))
    assert resp.status_code == 204, resp.text
    assert client.get(f"/api/v1/issues/{issue['key']}", headers=_auth(token)).status_code == 404


def test_delete_issue_forbidden_for_plain_member(client: TestClient) -> None:
    _, lead_token = _make_user(client, "dlead@example.com")
    _make_user(client, "dmember@example.com")
    proj = _create_project(client, lead_token, key="DLM")
    _add_member(client, lead_token, proj["id"], "dmember@example.com", "member")
    # Le lead (reporter) crée l'issue ; un simple membre non-reporter ne peut pas la supprimer.
    issue = _create_issue(client, lead_token, proj["id"])
    member_token = _login(client, "dmember@example.com")
    resp = client.delete(f"/api/v1/issues/{issue['key']}", headers=_auth(member_token))
    assert resp.status_code == 403, resp.text


def test_delete_issue_by_project_admin(client: TestClient) -> None:
    _, lead_token = _make_user(client, "dpa_lead@example.com")
    reporter, _ = _make_user(client, "dpa_rep@example.com")
    proj = _create_project(client, lead_token, key="DPA")
    _add_member(client, lead_token, proj["id"], "dpa_rep@example.com", "member")
    reporter_token = _login(client, "dpa_rep@example.com")
    issue = _create_issue(client, reporter_token, proj["id"])
    # Le lead/admin projet peut supprimer l'issue d'un autre.
    resp = client.delete(f"/api/v1/issues/{issue['key']}", headers=_auth(lead_token))
    assert resp.status_code == 204, resp.text


def test_delete_issue_unknown_404(client: TestClient) -> None:
    _, token = _make_user(client, "d404@example.com")
    resp = client.delete("/api/v1/issues/NOPE-1", headers=_auth(token))
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------------- #
# Hiérarchie Epic <-> enfants (JIR-35)
# --------------------------------------------------------------------------- #
def test_attach_story_to_epic(client: TestClient) -> None:
    _, token = _make_user(client, "hier@example.com")
    proj = _create_project(client, token, key="HIE")
    epic = _create_issue(client, token, proj["id"], type="epic", summary="Epic")
    story = _create_issue(client, token, proj["id"], type="story", epic_id=epic["id"])
    assert story["epic_id"] == epic["id"]


def test_epic_id_pointing_to_non_epic_422(client: TestClient) -> None:
    _, token = _make_user(client, "nonepic@example.com")
    proj = _create_project(client, token, key="NEP")
    task = _create_issue(client, token, proj["id"], type="task", summary="not an epic")
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/issues",
        json={"type": "story", "summary": "child", "epic_id": task["id"]},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text


def test_epic_cannot_have_epic_parent_422(client: TestClient) -> None:
    _, token = _make_user(client, "epicparent@example.com")
    proj = _create_project(client, token, key="ECP")
    epic = _create_issue(client, token, proj["id"], type="epic", summary="Parent epic")
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/issues",
        json={"type": "epic", "summary": "child epic", "epic_id": epic["id"]},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text


def test_epic_detail_exposes_children_and_progress(client: TestClient) -> None:
    _, token = _make_user(client, "progress@example.com")
    proj = _create_project(client, token, key="PRG")
    epic = _create_issue(client, token, proj["id"], type="epic", summary="Epic")
    c1 = _create_issue(client, token, proj["id"], type="story", epic_id=epic["id"])
    c2 = _create_issue(client, token, proj["id"], type="task", epic_id=epic["id"])
    client.patch(f"/api/v1/issues/{c1['key']}", json={"status": "done"}, headers=_auth(token))

    detail = client.get(f"/api/v1/issues/{epic['key']}", headers=_auth(token)).json()
    child_keys = {c["key"] for c in detail["children"]}
    assert child_keys == {c1["key"], c2["key"]}
    assert detail["progress"] == {"done": 1, "total": 2}


def test_epic_id_other_project_422(client: TestClient) -> None:
    _, token = _make_user(client, "xproj@example.com")
    proj_a = _create_project(client, token, key="XPA")
    proj_b = _create_project(client, token, key="XPB")
    epic_b = _create_issue(client, token, proj_b["id"], type="epic", summary="Epic B")
    resp = client.post(
        f"/api/v1/projects/{proj_a['id']}/issues",
        json={"type": "story", "summary": "child", "epic_id": epic_b["id"]},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text
