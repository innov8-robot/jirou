"""Tests d'intégration du BOARD KANBAN (EPIC-06, JIR-40).

Couvre :

- ``GET /projects/{id}/board`` : 4 colonnes dans l'ordre figé, placement des
  issues selon leur statut, tri par position, filtres cumulables, 403 pour un
  non-membre.
- ``PATCH /issues/{key}/move`` : changement de statut, renormalisation des
  positions, réordonnancement intra-colonne, garde-fous (viewer 403, clé
  inconnue 404), clamp de position hors bornes.

Réutilise les fixtures de ``conftest`` et le flux d'inscription/connexion.
"""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

VALID_PASSWORD = "s3cretpwd"

BOARD_ORDER = ["todo", "in_progress", "in_review", "done"]


# --------------------------------------------------------------------------- #
# Helpers (alignés sur test_issues.py)
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


def _get_board(client: TestClient, token: str, project_id: int, query: str = "") -> dict:
    resp = client.get(f"/api/v1/projects/{project_id}/board{query}", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _column(board: dict, status: str) -> list[dict]:
    for col in board["columns"]:
        if col["status"] == status:
            return col["issues"]
    raise AssertionError(f"colonne {status!r} absente")


def _move(client: TestClient, token: str, key: str, status: str, position: int) -> httpx.Response:
    return client.patch(
        f"/api/v1/issues/{key}/move",
        json={"status": status, "position": position},
        headers=_auth(token),
    )


# --------------------------------------------------------------------------- #
# GET /projects/{id}/board
# --------------------------------------------------------------------------- #
def test_board_four_columns_in_order_even_empty(client: TestClient) -> None:
    _, token = _make_user(client, "board1@example.com")
    proj = _create_project(client, token, key="BRD")
    board = _get_board(client, token, proj["id"])
    assert [col["status"] for col in board["columns"]] == BOARD_ORDER
    for col in board["columns"]:
        assert col["issues"] == []


def test_board_places_issues_in_right_column(client: TestClient) -> None:
    _, token = _make_user(client, "board2@example.com")
    proj = _create_project(client, token, key="PLC")
    todo = _create_issue(client, token, proj["id"], summary="a todo")
    prog = _create_issue(client, token, proj["id"], summary="in progress")
    _set_status(client, token, prog["key"], "in_progress")
    done = _create_issue(client, token, proj["id"], summary="finished")
    _set_status(client, token, done["key"], "done")

    board = _get_board(client, token, proj["id"])
    assert [i["key"] for i in _column(board, "todo")] == [todo["key"]]
    assert [i["key"] for i in _column(board, "in_progress")] == [prog["key"]]
    assert _column(board, "in_review") == []
    assert [i["key"] for i in _column(board, "done")] == [done["key"]]


def test_board_column_sorted_by_position(client: TestClient) -> None:
    _, token = _make_user(client, "board3@example.com")
    proj = _create_project(client, token, key="SRT")
    a = _create_issue(client, token, proj["id"], summary="A")
    b = _create_issue(client, token, proj["id"], summary="B")
    c = _create_issue(client, token, proj["id"], summary="C")
    # Toutes en todo (position 0 par défaut) ; on impose un ordre via move.
    _move(client, token, c["key"], "todo", 0)
    _move(client, token, a["key"], "todo", 1)
    _move(client, token, b["key"], "todo", 2)

    board = _get_board(client, token, proj["id"])
    positions = [i["position"] for i in _column(board, "todo")]
    assert positions == [0, 1, 2]
    assert [i["key"] for i in _column(board, "todo")] == [c["key"], a["key"], b["key"]]


def test_board_includes_read_relations(client: TestClient) -> None:
    profile, token = _make_user(client, "board4@example.com")
    proj = _create_project(client, token, key="REL")
    label = client.post(
        f"/api/v1/projects/{proj['id']}/labels",
        json={"name": "urgent", "color": "#ff0000"},
        headers=_auth(token),
    ).json()
    _create_issue(client, token, proj["id"], assignee_id=profile["id"], label_ids=[label["id"]])
    board = _get_board(client, token, proj["id"])
    card = _column(board, "todo")[0]
    assert card["assignee"]["id"] == profile["id"]
    assert card["reporter"]["id"] == profile["id"]
    assert [lbl["name"] for lbl in card["labels"]] == ["urgent"]


def test_board_filters_assignee_and_type(client: TestClient) -> None:
    profile, token = _make_user(client, "board5@example.com")
    proj = _create_project(client, token, key="FLT")
    mine_bug = _create_issue(
        client, token, proj["id"], type="bug", summary="mine", assignee_id=profile["id"]
    )
    _create_issue(client, token, proj["id"], type="task", summary="unassigned")

    by_assignee = _get_board(client, token, proj["id"], f"?assignee_id={profile['id']}")
    assert [i["key"] for i in _column(by_assignee, "todo")] == [mine_bug["key"]]

    by_type = _get_board(client, token, proj["id"], "?type=bug")
    assert [i["key"] for i in _column(by_type, "todo")] == [mine_bug["key"]]

    # Filtres cumulables.
    both = _get_board(client, token, proj["id"], f"?type=bug&assignee_id={profile['id']}")
    assert [i["key"] for i in _column(both, "todo")] == [mine_bug["key"]]


def test_board_non_member_forbidden(client: TestClient) -> None:
    _, token = _make_user(client, "board_owner@example.com")
    _, stranger = _make_user(client, "board_stranger@example.com")
    proj = _create_project(client, token, key="NMB")
    resp = client.get(f"/api/v1/projects/{proj['id']}/board", headers=_auth(stranger))
    assert resp.status_code == 403, resp.text


def test_board_unknown_project_404(client: TestClient) -> None:
    _, token = _make_user(client, "board_404@example.com")
    resp = client.get("/api/v1/projects/999999/board", headers=_auth(token))
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------------- #
# PATCH /issues/{key}/move
# --------------------------------------------------------------------------- #
def test_move_changes_status(client: TestClient) -> None:
    _, token = _make_user(client, "move1@example.com")
    proj = _create_project(client, token, key="MVS")
    issue = _create_issue(client, token, proj["id"])
    resp = _move(client, token, issue["key"], "in_progress", 0)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "in_progress"

    board = _get_board(client, token, proj["id"])
    assert _column(board, "todo") == []
    assert [i["key"] for i in _column(board, "in_progress")] == [issue["key"]]


def test_move_renormalizes_destination_positions(client: TestClient) -> None:
    _, token = _make_user(client, "move2@example.com")
    proj = _create_project(client, token, key="RNM")
    a = _create_issue(client, token, proj["id"], summary="A")
    b = _create_issue(client, token, proj["id"], summary="B")
    _set_status(client, token, a["key"], "in_progress")
    _set_status(client, token, b["key"], "in_progress")
    c = _create_issue(client, token, proj["id"], summary="C")

    # Insère C en tête de in_progress.
    _move(client, token, c["key"], "in_progress", 0)
    board = _get_board(client, token, proj["id"])
    col = _column(board, "in_progress")
    assert [i["position"] for i in col] == [0, 1, 2]
    assert col[0]["key"] == c["key"]


def test_move_reorder_within_same_column(client: TestClient) -> None:
    _, token = _make_user(client, "move3@example.com")
    proj = _create_project(client, token, key="ROC")
    a = _create_issue(client, token, proj["id"], summary="A")
    b = _create_issue(client, token, proj["id"], summary="B")
    c = _create_issue(client, token, proj["id"], summary="C")
    # Établit un ordre déterministe A,B,C dans todo.
    _move(client, token, a["key"], "todo", 0)
    _move(client, token, b["key"], "todo", 1)
    _move(client, token, c["key"], "todo", 2)

    # Déplace A de l'index 0 vers l'index 2.
    _move(client, token, a["key"], "todo", 2)
    board = _get_board(client, token, proj["id"])
    assert [i["key"] for i in _column(board, "todo")] == [b["key"], c["key"], a["key"]]


def test_move_out_of_bounds_position_clamped(client: TestClient) -> None:
    _, token = _make_user(client, "move4@example.com")
    proj = _create_project(client, token, key="CLP")
    a = _create_issue(client, token, proj["id"], summary="A")
    b = _create_issue(client, token, proj["id"], summary="B")
    _move(client, token, a["key"], "todo", 0)
    _move(client, token, b["key"], "todo", 1)

    # Position démesurée -> clampée à la fin (pas d'erreur).
    resp = _move(client, token, a["key"], "todo", 999)
    assert resp.status_code == 200, resp.text
    board = _get_board(client, token, proj["id"])
    col = _column(board, "todo")
    assert [i["key"] for i in col] == [b["key"], a["key"]]
    assert [i["position"] for i in col] == [0, 1]


def test_move_viewer_forbidden(client: TestClient) -> None:
    _, lead_token = _make_user(client, "mv_lead@example.com")
    _make_user(client, "mv_view@example.com")
    proj = _create_project(client, lead_token, key="MVW")
    _add_member(client, lead_token, proj["id"], "mv_view@example.com", "viewer")
    issue = _create_issue(client, lead_token, proj["id"])
    viewer_token = _login(client, "mv_view@example.com")
    resp = _move(client, viewer_token, issue["key"], "in_progress", 0)
    assert resp.status_code == 403, resp.text


def test_move_unknown_key_404(client: TestClient) -> None:
    _, token = _make_user(client, "mv_404@example.com")
    resp = _move(client, token, "NOPE-999", "in_progress", 0)
    assert resp.status_code == 404, resp.text


def test_move_invalid_status_422(client: TestClient) -> None:
    _, token = _make_user(client, "mv_422@example.com")
    proj = _create_project(client, token, key="MST")
    issue = _create_issue(client, token, proj["id"])
    resp = client.patch(
        f"/api/v1/issues/{issue['key']}/move",
        json={"status": "not_a_status", "position": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text


def test_positions_stay_consecutive_after_many_moves(client: TestClient) -> None:
    _, token = _make_user(client, "consist@example.com")
    proj = _create_project(client, token, key="CNS")
    keys = [_create_issue(client, token, proj["id"], summary=f"I{n}")["key"] for n in range(5)]

    # Enchaîne des déplacements variés entre colonnes et rangs.
    _move(client, token, keys[0], "in_progress", 0)
    _move(client, token, keys[1], "in_progress", 0)
    _move(client, token, keys[2], "done", 0)
    _move(client, token, keys[3], "in_progress", 1)
    _move(client, token, keys[0], "done", 5)
    _move(client, token, keys[4], "todo", 0)

    board = _get_board(client, token, proj["id"])
    for status in BOARD_ORDER:
        positions = [i["position"] for i in _column(board, status)]
        assert positions == list(range(len(positions))), (status, positions)
