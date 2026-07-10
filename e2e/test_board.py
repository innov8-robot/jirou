"""Board Kanban (EPIC-06) — end-to-end contre l'API réelle."""

from __future__ import annotations

import uuid

import httpx

from conftest import unique_email


def _key() -> str:
    return ('T' + uuid.uuid4().hex[:4]).upper()


def _project(api: httpx.Client, header: dict) -> dict:
    return api.post(
        '/projects', headers=header, json={'name': 'Board', 'key': _key()}
    ).json()


def _issue(api: httpx.Client, header: dict, project_id, summary: str) -> dict:
    return api.post(
        f'/projects/{project_id}/issues',
        headers=header,
        json={'type': 'task', 'summary': summary},
    ).json()


def _make_user(api: httpx.Client) -> dict:
    email = unique_email()
    api.post(
        '/auth/register',
        json={'email': email, 'password': 'password123', 'full_name': 'U'},
    )
    tokens = api.post(
        '/auth/login', json={'email': email, 'password': 'password123'}
    ).json()
    return {
        'email': email,
        'auth_header': {'Authorization': f"Bearer {tokens['access_token']}"},
    }


def _statuses(board: dict) -> list[str]:
    return [c['status'] for c in board['columns']]


def _find_col(board: dict, status: str) -> dict:
    return next(c for c in board['columns'] if c['status'] == status)


def test_board_has_four_ordered_columns(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    _issue(api, h, project['id'], 'A')

    board = api.get(f"/projects/{project['id']}/board", headers=h)
    assert board.status_code == 200, board.text
    assert _statuses(board.json()) == ['todo', 'in_progress', 'in_review', 'done']
    assert len(_find_col(board.json(), 'todo')['issues']) == 1


def test_move_changes_status(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    issue = _issue(api, h, project['id'], 'To move')

    r = api.patch(
        f"/issues/{issue['key']}/move",
        headers=h,
        json={'status': 'in_progress', 'position': 0},
    )
    assert r.status_code == 200, r.text
    assert r.json()['status'] == 'in_progress'

    board = api.get(f"/projects/{project['id']}/board", headers=h).json()
    assert len(_find_col(board, 'todo')['issues']) == 0
    assert any(
        i['key'] == issue['key'] for i in _find_col(board, 'in_progress')['issues']
    )


def test_reorder_within_column(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    a = _issue(api, h, project['id'], 'A')
    b = _issue(api, h, project['id'], 'B')
    c = _issue(api, h, project['id'], 'C')

    # Déplace A (index 0) en dernier (index 2) dans la colonne todo.
    api.patch(
        f"/issues/{a['key']}/move",
        headers=h,
        json={'status': 'todo', 'position': 2},
    )
    board = api.get(f"/projects/{project['id']}/board", headers=h).json()
    todo_keys = [i['key'] for i in _find_col(board, 'todo')['issues']]
    assert todo_keys == [b['key'], c['key'], a['key']]


def test_viewer_cannot_move(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    issue = _issue(api, h, project['id'], 'X')
    viewer = _make_user(api)
    api.post(
        f"/projects/{project['id']}/members",
        headers=h,
        json={'email': viewer['email'], 'role': 'viewer'},
    )
    r = api.patch(
        f"/issues/{issue['key']}/move",
        headers=viewer['auth_header'],
        json={'status': 'done', 'position': 0},
    )
    assert r.status_code == 403


def test_non_member_cannot_view_board(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    other = _make_user(api)
    r = api.get(
        f"/projects/{project['id']}/board", headers=other['auth_header']
    )
    assert r.status_code == 403
