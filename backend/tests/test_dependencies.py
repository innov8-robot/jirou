"""Tests d'intégration des DÉPENDANCES entre tickets (EPIC-08, JIR-61).

Couvre la création (201), les erreurs (doublon 409, auto-dépendance 422, cible
d'un autre projet 422, cible inconnue 404), la suppression (204), l'interdiction
des viewers (403) et l'exposition des dépendances (avec la bonne ``direction``)
dans ``IssueDetail`` des deux côtés.
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


def _create_dep(client: TestClient, token: str, from_key: str, target_key: str, **fields: object):
    return client.post(
        f"/api/v1/issues/{from_key}/dependencies",
        json={"target_key": target_key, **fields},
        headers=_auth(token),
    )


# --------------------------------------------------------------------------- #
# POST /issues/{key}/dependencies
# --------------------------------------------------------------------------- #
def test_create_dependency_201(client: TestClient) -> None:
    _, token = _make_user(client, "dep1@example.com")
    proj = _create_project(client, token, key="DEP")
    a = _create_issue(client, token, proj["id"], summary="A")
    b = _create_issue(client, token, proj["id"], summary="B")

    resp = _create_dep(client, token, a["key"], b["key"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["type"] == "blocks"
    assert body["from"]["key"] == a["key"]
    assert body["to"]["key"] == b["key"]
    assert set(body["from"].keys()) == {"id", "key", "summary", "type", "status"}
    assert "id" in body


def test_create_dependency_duplicate_409(client: TestClient) -> None:
    _, token = _make_user(client, "dep2@example.com")
    proj = _create_project(client, token, key="DPB")
    a = _create_issue(client, token, proj["id"])
    b = _create_issue(client, token, proj["id"])

    assert _create_dep(client, token, a["key"], b["key"]).status_code == 201
    resp = _create_dep(client, token, a["key"], b["key"])
    assert resp.status_code == 409, resp.text


def test_create_dependency_self_422(client: TestClient) -> None:
    _, token = _make_user(client, "dep3@example.com")
    proj = _create_project(client, token, key="DPC")
    a = _create_issue(client, token, proj["id"])

    resp = _create_dep(client, token, a["key"], a["key"])
    assert resp.status_code == 422, resp.text


def test_create_dependency_other_project_422(client: TestClient) -> None:
    _, token = _make_user(client, "dep4@example.com")
    proj_a = _create_project(client, token, key="DPD")
    proj_b = _create_project(client, token, key="DPE")
    a = _create_issue(client, token, proj_a["id"])
    b = _create_issue(client, token, proj_b["id"])

    resp = _create_dep(client, token, a["key"], b["key"])
    assert resp.status_code == 422, resp.text


def test_create_dependency_target_unknown_404(client: TestClient) -> None:
    _, token = _make_user(client, "dep5@example.com")
    proj = _create_project(client, token, key="DPF")
    a = _create_issue(client, token, proj["id"])

    resp = _create_dep(client, token, a["key"], "DPF-999")
    assert resp.status_code == 404, resp.text


def test_create_dependency_source_unknown_404(client: TestClient) -> None:
    _, token = _make_user(client, "dep6@example.com")
    proj = _create_project(client, token, key="DPG")
    b = _create_issue(client, token, proj["id"])

    resp = _create_dep(client, token, "DPG-999", b["key"])
    assert resp.status_code == 404, resp.text


def test_create_dependency_viewer_forbidden_403(client: TestClient) -> None:
    _, lead_token = _make_user(client, "leaddep@example.com")
    _make_user(client, "viewerdep@example.com")
    proj = _create_project(client, lead_token, key="DPH")
    _add_member(client, lead_token, proj["id"], "viewerdep@example.com", "viewer")
    viewer_token = _login(client, "viewerdep@example.com")
    a = _create_issue(client, lead_token, proj["id"])
    b = _create_issue(client, lead_token, proj["id"])

    resp = _create_dep(client, viewer_token, a["key"], b["key"])
    assert resp.status_code == 403, resp.text


def test_create_dependency_inverse_cycle_409(client: TestClient) -> None:
    _, token = _make_user(client, "dep7@example.com")
    proj = _create_project(client, token, key="DPI")
    a = _create_issue(client, token, proj["id"])
    b = _create_issue(client, token, proj["id"])

    assert _create_dep(client, token, a["key"], b["key"]).status_code == 201
    # B bloque A alors que A bloque déjà B : cycle direct refusé.
    resp = _create_dep(client, token, b["key"], a["key"])
    assert resp.status_code == 409, resp.text


# --------------------------------------------------------------------------- #
# DELETE /issues/{key}/dependencies/{id}
# --------------------------------------------------------------------------- #
def test_delete_dependency_204(client: TestClient) -> None:
    _, token = _make_user(client, "dep8@example.com")
    proj = _create_project(client, token, key="DPJ")
    a = _create_issue(client, token, proj["id"])
    b = _create_issue(client, token, proj["id"])
    dep = _create_dep(client, token, a["key"], b["key"]).json()

    resp = client.delete(
        f"/api/v1/issues/{a['key']}/dependencies/{dep['id']}",
        headers=_auth(token),
    )
    assert resp.status_code == 204, resp.text
    # La dépendance a disparu du détail.
    detail = client.get(f"/api/v1/issues/{a['key']}", headers=_auth(token)).json()
    assert detail["dependencies"] == []


def test_delete_dependency_unknown_404(client: TestClient) -> None:
    _, token = _make_user(client, "dep9@example.com")
    proj = _create_project(client, token, key="DPK")
    a = _create_issue(client, token, proj["id"])

    resp = client.delete(
        f"/api/v1/issues/{a['key']}/dependencies/99999",
        headers=_auth(token),
    )
    assert resp.status_code == 404, resp.text


def test_delete_dependency_viewer_forbidden_403(client: TestClient) -> None:
    _, lead_token = _make_user(client, "leaddel@example.com")
    _make_user(client, "viewerdel@example.com")
    proj = _create_project(client, lead_token, key="DPL")
    _add_member(client, lead_token, proj["id"], "viewerdel@example.com", "viewer")
    viewer_token = _login(client, "viewerdel@example.com")
    a = _create_issue(client, lead_token, proj["id"])
    b = _create_issue(client, lead_token, proj["id"])
    dep = _create_dep(client, lead_token, a["key"], b["key"]).json()

    resp = client.delete(
        f"/api/v1/issues/{a['key']}/dependencies/{dep['id']}",
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------------- #
# IssueDetail.dependencies (direction outward/inward)
# --------------------------------------------------------------------------- #
def test_issue_detail_exposes_dependencies_directions(client: TestClient) -> None:
    _, token = _make_user(client, "dep10@example.com")
    proj = _create_project(client, token, key="DPM")
    a = _create_issue(client, token, proj["id"], summary="A")
    b = _create_issue(client, token, proj["id"], summary="B")
    # A bloque B.
    _create_dep(client, token, a["key"], b["key"])

    detail_a = client.get(f"/api/v1/issues/{a['key']}", headers=_auth(token)).json()
    assert len(detail_a["dependencies"]) == 1
    link_a = detail_a["dependencies"][0]
    assert link_a["direction"] == "outward"
    assert link_a["issue"]["key"] == b["key"]
    assert link_a["type"] == "blocks"

    detail_b = client.get(f"/api/v1/issues/{b['key']}", headers=_auth(token)).json()
    assert len(detail_b["dependencies"]) == 1
    link_b = detail_b["dependencies"][0]
    assert link_b["direction"] == "inward"
    assert link_b["issue"]["key"] == a["key"]
