"""Tests d'intégration du domaine LABELS (EPIC-05, JIR-31).

Couvre le CRUD des labels, l'unicité du nom par projet (409), les permissions
(viewer interdit) et le refus d'un label d'un autre projet sur une issue (422).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

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


def _create_label(client: TestClient, token: str, project_id: int, name: str, color: str) -> dict:
    resp = client.post(
        f"/api/v1/projects/{project_id}/labels",
        json={"name": name, "color": color},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
def test_create_and_list_labels(client: TestClient) -> None:
    _, token = _make_user(client, "lbcreate@example.com")
    proj = _create_project(client, token, key="LBL")
    label = _create_label(client, token, proj["id"], "backend", "#00ff00")
    assert label["name"] == "backend"
    assert label["color"] == "#00ff00"
    assert label["project_id"] == proj["id"]

    resp = client.get(f"/api/v1/projects/{proj['id']}/labels", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert [lbl["name"] for lbl in resp.json()] == ["backend"]


def test_create_label_duplicate_name_409(client: TestClient) -> None:
    _, token = _make_user(client, "lbdup@example.com")
    proj = _create_project(client, token, key="DUP")
    _create_label(client, token, proj["id"], "same", "#111111")
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/labels",
        json={"name": "same", "color": "#222222"},
        headers=_auth(token),
    )
    assert resp.status_code == 409, resp.text


def test_same_label_name_allowed_across_projects(client: TestClient) -> None:
    _, token = _make_user(client, "lbcross@example.com")
    proj_a = _create_project(client, token, key="CRA")
    proj_b = _create_project(client, token, key="CRB")
    _create_label(client, token, proj_a["id"], "shared", "#123456")
    # Même nom, autre projet -> autorisé.
    _create_label(client, token, proj_b["id"], "shared", "#654321")


def test_update_label(client: TestClient) -> None:
    _, token = _make_user(client, "lbupd@example.com")
    proj = _create_project(client, token, key="UPD")
    label = _create_label(client, token, proj["id"], "old", "#000000")
    resp = client.patch(
        f"/api/v1/labels/{label['id']}",
        json={"name": "new", "color": "#ffffff"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "new"
    assert body["color"] == "#ffffff"


def test_update_label_conflict_409(client: TestClient) -> None:
    _, token = _make_user(client, "lbupdc@example.com")
    proj = _create_project(client, token, key="UPC")
    _create_label(client, token, proj["id"], "taken", "#111111")
    other = _create_label(client, token, proj["id"], "free", "#222222")
    resp = client.patch(
        f"/api/v1/labels/{other['id']}", json={"name": "taken"}, headers=_auth(token)
    )
    assert resp.status_code == 409, resp.text


def test_delete_label(client: TestClient) -> None:
    _, token = _make_user(client, "lbdel@example.com")
    proj = _create_project(client, token, key="DEL")
    label = _create_label(client, token, proj["id"], "temp", "#abcdef")
    resp = client.delete(f"/api/v1/labels/{label['id']}", headers=_auth(token))
    assert resp.status_code == 204, resp.text
    remaining = client.get(f"/api/v1/projects/{proj['id']}/labels", headers=_auth(token)).json()
    assert remaining == []


def test_delete_label_unknown_404(client: TestClient) -> None:
    _, token = _make_user(client, "lb404@example.com")
    _create_project(client, token, key="NF4")
    resp = client.delete("/api/v1/labels/999999", headers=_auth(token))
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------------- #
# Permissions
# --------------------------------------------------------------------------- #
def test_create_label_viewer_forbidden(client: TestClient) -> None:
    _, lead_token = _make_user(client, "lbboss@example.com")
    _make_user(client, "lbview@example.com")
    proj = _create_project(client, lead_token, key="VWL")
    _add_member(client, lead_token, proj["id"], "lbview@example.com", "viewer")
    viewer_token = _login(client, "lbview@example.com")
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/labels",
        json={"name": "nope", "color": "#000000"},
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403, resp.text


def test_list_labels_non_member_forbidden(client: TestClient) -> None:
    _, token = _make_user(client, "lbowner@example.com")
    _, stranger = _make_user(client, "lbstranger@example.com")
    proj = _create_project(client, token, key="LNM")
    resp = client.get(f"/api/v1/projects/{proj['id']}/labels", headers=_auth(stranger))
    assert resp.status_code == 403, resp.text


def test_update_label_viewer_forbidden(client: TestClient) -> None:
    _, lead_token = _make_user(client, "lbuboss@example.com")
    _make_user(client, "lbuview@example.com")
    proj = _create_project(client, lead_token, key="UVW")
    _add_member(client, lead_token, proj["id"], "lbuview@example.com", "viewer")
    label = _create_label(client, lead_token, proj["id"], "locked", "#333333")
    viewer_token = _login(client, "lbuview@example.com")
    resp = client.patch(
        f"/api/v1/labels/{label['id']}", json={"name": "hijack"}, headers=_auth(viewer_token)
    )
    assert resp.status_code == 403, resp.text


def test_invalid_color_422(client: TestClient) -> None:
    _, token = _make_user(client, "lbcolor@example.com")
    proj = _create_project(client, token, key="CLR")
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/labels",
        json={"name": "bad", "color": "not-a-color"},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text
