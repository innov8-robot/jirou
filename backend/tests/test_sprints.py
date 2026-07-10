"""Tests d'intégration des SPRINTS, BACKLOG & reporting (EPIC-07, JIR-47/48/54).

Couvre :

- ``POST/GET /projects/{id}/sprints`` : création (future), 403 viewer.
- ``POST /sprints/{id}/start`` : passage active, 409 si déjà un actif ; PATCH dates.
- ``PATCH /issues/{key}/backlog-move`` : backlog↔sprint, réordonnancement,
  renormalisation, 422 sprint d'un autre projet.
- ``GET /projects/{id}/backlog`` : backlog vs sprints, sommes de points.
- ``POST /sprints/{id}/complete`` : snapshots committed/completed, issues done
  conservées, non-done déplacées (backlog ET next), 400 si non actif.
- ``DELETE /sprints/{id}`` : issues renvoyées au backlog.
- ``GET /projects/{id}/velocity``.
- filtre ``sprint_id`` du board.

Réutilise les fixtures de ``conftest`` et le flux d'inscription/connexion.
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


def _set_status(client: TestClient, token: str, key: str, status: str) -> None:
    resp = client.patch(f"/api/v1/issues/{key}", json={"status": status}, headers=_auth(token))
    assert resp.status_code == 200, resp.text


def _create_sprint(client: TestClient, token: str, project_id: int, name: str = "Sprint 1", **f):
    resp = client.post(
        f"/api/v1/projects/{project_id}/sprints",
        json={"name": name, **f},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _backlog_move(client, token, key, sprint_id, position):
    return client.patch(
        f"/api/v1/issues/{key}/backlog-move",
        json={"sprint_id": sprint_id, "position": position},
        headers=_auth(token),
    )


def _get_backlog(client, token, project_id, query: str = "") -> dict:
    resp = client.get(f"/api/v1/projects/{project_id}/backlog{query}", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# Création / lecture
# --------------------------------------------------------------------------- #
def test_create_sprint_is_future(client: TestClient) -> None:
    _, token = _make_user(client, "sp_create@example.com")
    proj = _create_project(client, token, key="SPC")
    sprint = _create_sprint(client, token, proj["id"], name="Sprint Alpha", goal="Ship it")
    assert sprint["status"] == "future"
    assert sprint["name"] == "Sprint Alpha"
    assert sprint["goal"] == "Ship it"
    assert sprint["committed_points"] == 0
    assert sprint["completed_points"] == 0
    assert sprint["issue_count"] == 0

    listing = client.get(f"/api/v1/projects/{proj['id']}/sprints", headers=_auth(token))
    assert listing.status_code == 200
    assert [s["id"] for s in listing.json()] == [sprint["id"]]


def test_create_sprint_viewer_forbidden(client: TestClient) -> None:
    _, lead_token = _make_user(client, "sp_lead@example.com")
    _make_user(client, "sp_view@example.com")
    proj = _create_project(client, lead_token, key="SPV")
    _add_member(client, lead_token, proj["id"], "sp_view@example.com", "viewer")
    viewer_token = _login(client, "sp_view@example.com")
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/sprints",
        json={"name": "Nope"},
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403, resp.text


def test_create_sprint_unknown_project_404(client: TestClient) -> None:
    _, token = _make_user(client, "sp_404@example.com")
    resp = client.post("/api/v1/projects/999999/sprints", json={"name": "X"}, headers=_auth(token))
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# start / patch dates
# --------------------------------------------------------------------------- #
def test_start_sprint_becomes_active(client: TestClient) -> None:
    _, token = _make_user(client, "sp_start@example.com")
    proj = _create_project(client, token, key="STA")
    sprint = _create_sprint(client, token, proj["id"])
    resp = client.post(
        f"/api/v1/sprints/{sprint['id']}/start",
        json={"start_date": "2026-07-01", "end_date": "2026-07-14"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "active"
    assert body["start_date"] == "2026-07-01"
    assert body["end_date"] == "2026-07-14"


def test_start_second_sprint_conflicts(client: TestClient) -> None:
    _, token = _make_user(client, "sp_conflict@example.com")
    proj = _create_project(client, token, key="CFL")
    s1 = _create_sprint(client, token, proj["id"], name="S1")
    s2 = _create_sprint(client, token, proj["id"], name="S2")
    r1 = client.post(f"/api/v1/sprints/{s1['id']}/start", json={}, headers=_auth(token))
    assert r1.status_code == 200
    r2 = client.post(f"/api/v1/sprints/{s2['id']}/start", json={}, headers=_auth(token))
    assert r2.status_code == 409, r2.text


def test_patch_sprint_dates(client: TestClient) -> None:
    _, token = _make_user(client, "sp_patch@example.com")
    proj = _create_project(client, token, key="PAT")
    sprint = _create_sprint(client, token, proj["id"])
    resp = client.patch(
        f"/api/v1/sprints/{sprint['id']}",
        json={"name": "Renamed", "start_date": "2026-08-01", "end_date": "2026-08-15"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["start_date"] == "2026-08-01"
    assert body["end_date"] == "2026-08-15"


# --------------------------------------------------------------------------- #
# backlog-move + backlog view
# --------------------------------------------------------------------------- #
def test_backlog_move_and_view(client: TestClient) -> None:
    _, token = _make_user(client, "bl_move@example.com")
    proj = _create_project(client, token, key="BLM")
    sprint = _create_sprint(client, token, proj["id"])
    i1 = _create_issue(client, token, proj["id"], summary="A", story_points=3)
    i2 = _create_issue(client, token, proj["id"], summary="B", story_points=5)
    i3 = _create_issue(client, token, proj["id"], summary="C")  # points null -> 0

    # i1, i2 vers le sprint ; i3 reste au backlog.
    assert _backlog_move(client, token, i1["key"], sprint["id"], 0).status_code == 200
    r2 = _backlog_move(client, token, i2["key"], sprint["id"], 0)
    assert r2.status_code == 200
    assert r2.json()["sprint_id"] == sprint["id"]

    view = _get_backlog(client, token, proj["id"])
    # Backlog produit : uniquement i3 (points 0).
    assert [i["key"] for i in view["backlog"]["issues"]] == [i3["key"]]
    assert view["backlog"]["points"] == 0
    # Un seul bucket sprint.
    assert len(view["sprints"]) == 1
    bucket = view["sprints"][0]
    assert bucket["sprint"]["id"] == sprint["id"]
    assert bucket["points"] == 8  # 3 + 5
    # i2 inséré en tête (position 0), i1 ensuite.
    assert [i["key"] for i in bucket["issues"]] == [i2["key"], i1["key"]]
    assert [i["position"] for i in bucket["issues"]] == [0, 1]


def test_backlog_move_back_to_backlog_renormalizes(client: TestClient) -> None:
    _, token = _make_user(client, "bl_back@example.com")
    proj = _create_project(client, token, key="BLB")
    sprint = _create_sprint(client, token, proj["id"])
    a = _create_issue(client, token, proj["id"], summary="A")
    b = _create_issue(client, token, proj["id"], summary="B")
    c = _create_issue(client, token, proj["id"], summary="C")
    for idx, iss in enumerate([a, b, c]):
        assert _backlog_move(client, token, iss["key"], sprint["id"], idx).status_code == 200

    # Renvoie B au backlog -> sprint garde A,C renormalisés 0,1.
    resp = _backlog_move(client, token, b["key"], None, 0)
    assert resp.status_code == 200
    assert resp.json()["sprint_id"] is None

    view = _get_backlog(client, token, proj["id"])
    assert [i["key"] for i in view["backlog"]["issues"]] == [b["key"]]
    bucket = view["sprints"][0]
    assert [i["key"] for i in bucket["issues"]] == [a["key"], c["key"]]
    assert [i["position"] for i in bucket["issues"]] == [0, 1]


def test_backlog_move_reorder_within_sprint(client: TestClient) -> None:
    _, token = _make_user(client, "bl_reorder@example.com")
    proj = _create_project(client, token, key="BLR")
    sprint = _create_sprint(client, token, proj["id"])
    a = _create_issue(client, token, proj["id"], summary="A")
    b = _create_issue(client, token, proj["id"], summary="B")
    c = _create_issue(client, token, proj["id"], summary="C")
    for idx, iss in enumerate([a, b, c]):
        _backlog_move(client, token, iss["key"], sprint["id"], idx)

    # Déplace A en fin.
    _backlog_move(client, token, a["key"], sprint["id"], 2)
    bucket = _get_backlog(client, token, proj["id"])["sprints"][0]
    assert [i["key"] for i in bucket["issues"]] == [b["key"], c["key"], a["key"]]
    assert [i["position"] for i in bucket["issues"]] == [0, 1, 2]


def test_backlog_move_other_project_sprint_422(client: TestClient) -> None:
    _, token = _make_user(client, "bl_422@example.com")
    proj_a = _create_project(client, token, key="PJA")
    proj_b = _create_project(client, token, key="PJB")
    sprint_b = _create_sprint(client, token, proj_b["id"])
    issue_a = _create_issue(client, token, proj_a["id"], summary="A")
    resp = _backlog_move(client, token, issue_a["key"], sprint_b["id"], 0)
    assert resp.status_code == 422, resp.text


def test_backlog_move_viewer_forbidden(client: TestClient) -> None:
    _, lead_token = _make_user(client, "bl_lead@example.com")
    _make_user(client, "bl_view@example.com")
    proj = _create_project(client, lead_token, key="BLV")
    _add_member(client, lead_token, proj["id"], "bl_view@example.com", "viewer")
    sprint = _create_sprint(client, lead_token, proj["id"])
    issue = _create_issue(client, lead_token, proj["id"])
    viewer_token = _login(client, "bl_view@example.com")
    resp = _backlog_move(client, viewer_token, issue["key"], sprint["id"], 0)
    assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------------- #
# complete
# --------------------------------------------------------------------------- #
def test_complete_snapshots_and_moves_to_backlog(client: TestClient) -> None:
    _, token = _make_user(client, "cmp_bl@example.com")
    proj = _create_project(client, token, key="CMB")
    sprint = _create_sprint(client, token, proj["id"])
    done1 = _create_issue(client, token, proj["id"], summary="done1", story_points=3)
    done2 = _create_issue(client, token, proj["id"], summary="done2", story_points=2)
    todo = _create_issue(client, token, proj["id"], summary="todo", story_points=5)
    for iss in (done1, done2, todo):
        _backlog_move(client, token, iss["key"], sprint["id"], 0)
    _set_status(client, token, done1["key"], "done")
    _set_status(client, token, done2["key"], "done")
    client.post(f"/api/v1/sprints/{sprint['id']}/start", json={}, headers=_auth(token))

    resp = client.post(
        f"/api/v1/sprints/{sprint['id']}/complete",
        json={"move_incomplete_to": "backlog"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sprint"]["status"] == "completed"
    assert body["committed_points"] == 10  # 3 + 2 + 5
    assert body["completed_points"] == 5  # 3 + 2
    assert body["done_count"] == 2
    assert body["not_done_count"] == 1
    assert body["moved_to"] == "backlog"
    assert body["sprint"]["committed_points"] == 10
    assert body["sprint"]["completed_points"] == 5

    # done restent dans le sprint (issue_count = 2), todo repart au backlog.
    view = _get_backlog(client, token, proj["id"])
    assert [i["key"] for i in view["backlog"]["issues"]] == [todo["key"]]
    # Le sprint completed n'apparaît plus dans la vue backlog.
    assert view["sprints"] == []
    # Mais reste consultable via include_completed et garde ses issues done.
    listing = client.get(
        f"/api/v1/projects/{proj['id']}/sprints?include_completed=true", headers=_auth(token)
    ).json()
    assert listing[0]["issue_count"] == 2


def test_complete_move_to_next_sprint(client: TestClient) -> None:
    _, token = _make_user(client, "cmp_next@example.com")
    proj = _create_project(client, token, key="CMN")
    active = _create_sprint(client, token, proj["id"], name="Active")
    nxt = _create_sprint(client, token, proj["id"], name="Next")
    todo = _create_issue(client, token, proj["id"], summary="carry", story_points=8)
    _backlog_move(client, token, todo["key"], active["id"], 0)
    client.post(f"/api/v1/sprints/{active['id']}/start", json={}, headers=_auth(token))

    resp = client.post(
        f"/api/v1/sprints/{active['id']}/complete",
        json={"move_incomplete_to": "next"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["moved_to"] == f"sprint:{nxt['id']}"
    assert body["not_done_count"] == 1

    # L'issue non terminée est désormais dans le sprint "next".
    view = _get_backlog(client, token, proj["id"])
    next_bucket = next(b for b in view["sprints"] if b["sprint"]["id"] == nxt["id"])
    assert [i["key"] for i in next_bucket["issues"]] == [todo["key"]]


def test_complete_next_without_future_falls_back_to_backlog(client: TestClient) -> None:
    _, token = _make_user(client, "cmp_fb@example.com")
    proj = _create_project(client, token, key="CFB")
    active = _create_sprint(client, token, proj["id"], name="Active")
    todo = _create_issue(client, token, proj["id"], summary="carry")
    _backlog_move(client, token, todo["key"], active["id"], 0)
    client.post(f"/api/v1/sprints/{active['id']}/start", json={}, headers=_auth(token))
    resp = client.post(
        f"/api/v1/sprints/{active['id']}/complete",
        json={"move_incomplete_to": "next"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["moved_to"] == "backlog"


def test_complete_not_active_400(client: TestClient) -> None:
    _, token = _make_user(client, "cmp_400@example.com")
    proj = _create_project(client, token, key="C40")
    sprint = _create_sprint(client, token, proj["id"])
    resp = client.post(f"/api/v1/sprints/{sprint['id']}/complete", json={}, headers=_auth(token))
    assert resp.status_code == 400, resp.text


# --------------------------------------------------------------------------- #
# delete
# --------------------------------------------------------------------------- #
def test_delete_sprint_returns_issues_to_backlog(client: TestClient) -> None:
    _, token = _make_user(client, "del@example.com")
    proj = _create_project(client, token, key="DEL")
    sprint = _create_sprint(client, token, proj["id"])
    issue = _create_issue(client, token, proj["id"], summary="A", story_points=2)
    _backlog_move(client, token, issue["key"], sprint["id"], 0)

    resp = client.delete(f"/api/v1/sprints/{sprint['id']}", headers=_auth(token))
    assert resp.status_code == 204, resp.text

    view = _get_backlog(client, token, proj["id"])
    assert view["sprints"] == []
    assert [i["key"] for i in view["backlog"]["issues"]] == [issue["key"]]


# --------------------------------------------------------------------------- #
# velocity
# --------------------------------------------------------------------------- #
def test_velocity_returns_completed_sprints(client: TestClient) -> None:
    _, token = _make_user(client, "vel@example.com")
    proj = _create_project(client, token, key="VEL")
    sprint = _create_sprint(client, token, proj["id"], name="V1")
    done = _create_issue(client, token, proj["id"], summary="d", story_points=5)
    todo = _create_issue(client, token, proj["id"], summary="t", story_points=3)
    _backlog_move(client, token, done["key"], sprint["id"], 0)
    _backlog_move(client, token, todo["key"], sprint["id"], 1)
    _set_status(client, token, done["key"], "done")
    client.post(f"/api/v1/sprints/{sprint['id']}/start", json={}, headers=_auth(token))
    client.post(f"/api/v1/sprints/{sprint['id']}/complete", json={}, headers=_auth(token))

    resp = client.get(f"/api/v1/projects/{proj['id']}/velocity", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    points = resp.json()
    assert len(points) == 1
    assert points[0]["sprint_id"] == sprint["id"]
    assert points[0]["name"] == "V1"
    assert points[0]["committed_points"] == 8
    assert points[0]["completed_points"] == 5


def test_velocity_empty_without_completed(client: TestClient) -> None:
    _, token = _make_user(client, "vel_empty@example.com")
    proj = _create_project(client, token, key="VLE")
    _create_sprint(client, token, proj["id"])
    resp = client.get(f"/api/v1/projects/{proj['id']}/velocity", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []


# --------------------------------------------------------------------------- #
# board sprint_id filter
# --------------------------------------------------------------------------- #
def test_board_filters_by_sprint(client: TestClient) -> None:
    _, token = _make_user(client, "board_sp@example.com")
    proj = _create_project(client, token, key="BSP")
    sprint = _create_sprint(client, token, proj["id"])
    in_sprint = _create_issue(client, token, proj["id"], summary="in")
    _create_issue(client, token, proj["id"], summary="out")
    _backlog_move(client, token, in_sprint["key"], sprint["id"], 0)

    resp = client.get(
        f"/api/v1/projects/{proj['id']}/board?sprint_id={sprint['id']}", headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text
    board = resp.json()
    todo = next(c for c in board["columns"] if c["status"] == "todo")["issues"]
    assert [i["key"] for i in todo] == [in_sprint["key"]]
