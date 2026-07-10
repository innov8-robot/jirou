"""Sprints, Backlog & vélocité (EPIC-07) — end-to-end contre l'API réelle."""

from __future__ import annotations

import uuid

import httpx

from conftest import unique_email


def _key() -> str:
    return ('T' + uuid.uuid4().hex[:4]).upper()


def _project(api: httpx.Client, header: dict) -> dict:
    return api.post(
        '/projects', headers=header, json={'name': 'Sprintable', 'key': _key()}
    ).json()


def _issue(api, header, project_id, summary, points=None) -> dict:
    body = {'type': 'task', 'summary': summary}
    if points is not None:
        body['story_points'] = points
    return api.post(
        f'/projects/{project_id}/issues', headers=header, json=body
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


def test_create_sprint(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    r = api.post(
        f"/projects/{project['id']}/sprints", headers=h, json={'name': 'Sprint 1'}
    )
    assert r.status_code == 201, r.text
    assert r.json()['status'] == 'future'


def test_viewer_cannot_create_sprint(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    viewer = _make_user(api)
    api.post(
        f"/projects/{project['id']}/members",
        headers=h,
        json={'email': viewer['email'], 'role': 'viewer'},
    )
    r = api.post(
        f"/projects/{project['id']}/sprints",
        headers=viewer['auth_header'],
        json={'name': 'X'},
    )
    assert r.status_code == 403


def test_backlog_move_and_view(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    sprint = api.post(
        f"/projects/{project['id']}/sprints", headers=h, json={'name': 'S1'}
    ).json()
    issue = _issue(api, h, project['id'], 'Backlog item', points=3)

    # Initialement au backlog.
    backlog = api.get(f"/projects/{project['id']}/backlog", headers=h).json()
    assert any(i['key'] == issue['key'] for i in backlog['backlog']['issues'])

    # Déplace vers le sprint.
    mv = api.patch(
        f"/issues/{issue['key']}/backlog-move",
        headers=h,
        json={'sprint_id': sprint['id'], 'position': 0},
    )
    assert mv.status_code == 200, mv.text

    backlog2 = api.get(f"/projects/{project['id']}/backlog", headers=h).json()
    sprint_bucket = next(
        s for s in backlog2['sprints'] if s['sprint']['id'] == sprint['id']
    )
    assert any(i['key'] == issue['key'] for i in sprint_bucket['issues'])
    assert sprint_bucket['points'] == 3
    assert all(i['key'] != issue['key'] for i in backlog2['backlog']['issues'])


def test_start_conflict(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    s1 = api.post(
        f"/projects/{project['id']}/sprints", headers=h, json={'name': 'S1'}
    ).json()
    s2 = api.post(
        f"/projects/{project['id']}/sprints", headers=h, json={'name': 'S2'}
    ).json()
    assert api.post(f"/sprints/{s1['id']}/start", headers=h, json={}).status_code == 200
    assert api.post(f"/sprints/{s2['id']}/start", headers=h, json={}).status_code == 409


def test_complete_sprint_and_velocity(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    sprint = api.post(
        f"/projects/{project['id']}/sprints", headers=h, json={'name': 'S1'}
    ).json()
    done = _issue(api, h, project['id'], 'Done', points=5)
    todo = _issue(api, h, project['id'], 'Todo', points=3)
    for iss in (done, todo):
        api.patch(
            f"/issues/{iss['key']}/backlog-move",
            headers=h,
            json={'sprint_id': sprint['id'], 'position': 0},
        )
    api.patch(f"/issues/{done['key']}", headers=h, json={'status': 'done'})
    api.post(f"/sprints/{sprint['id']}/start", headers=h, json={})

    res = api.post(
        f"/sprints/{sprint['id']}/complete",
        headers=h,
        json={'move_incomplete_to': 'backlog'},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body['committed_points'] == 8
    assert body['completed_points'] == 5
    assert body['done_count'] == 1
    assert body['not_done_count'] == 1

    # Le ticket non terminé est revenu au backlog.
    backlog = api.get(f"/projects/{project['id']}/backlog", headers=h).json()
    assert any(i['key'] == todo['key'] for i in backlog['backlog']['issues'])

    # Vélocité.
    velo = api.get(f"/projects/{project['id']}/velocity", headers=h).json()
    entry = next(v for v in velo if v['sprint_id'] == sprint['id'])
    assert entry['committed_points'] == 8
    assert entry['completed_points'] == 5


def test_board_sprint_filter(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    sprint = api.post(
        f"/projects/{project['id']}/sprints", headers=h, json={'name': 'S1'}
    ).json()
    in_sprint = _issue(api, h, project['id'], 'In sprint')
    _issue(api, h, project['id'], 'In backlog')
    api.patch(
        f"/issues/{in_sprint['key']}/backlog-move",
        headers=h,
        json={'sprint_id': sprint['id'], 'position': 0},
    )
    board = api.get(
        f"/projects/{project['id']}/board",
        headers=h,
        params={'sprint_id': sprint['id']},
    ).json()
    keys = [i['key'] for c in board['columns'] for i in c['issues']]
    assert in_sprint['key'] in keys
    assert len(keys) == 1
