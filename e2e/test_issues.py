"""Tickets / Issues (EPIC-05) — end-to-end contre l'API réelle."""

from __future__ import annotations

import uuid

import httpx

from conftest import unique_email


def _key() -> str:
    return ('T' + uuid.uuid4().hex[:4]).upper()


def _make_project(api: httpx.Client, header: dict) -> dict:
    return api.post(
        '/projects', headers=header, json={'name': 'Proj', 'key': _key()}
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


def test_create_issue_and_key_sequence(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _make_project(api, h)

    r1 = api.post(
        f"/projects/{project['id']}/issues",
        headers=h,
        json={'type': 'story', 'summary': 'Première'},
    )
    assert r1.status_code == 201, r1.text
    issue1 = r1.json()
    assert issue1['key'] == f"{project['key']}-1"
    assert issue1['status'] == 'todo'
    assert issue1['priority'] == 'medium'
    assert issue1['reporter'] is not None

    r2 = api.post(
        f"/projects/{project['id']}/issues",
        headers=h,
        json={'type': 'bug', 'summary': 'Deuxième'},
    )
    assert r2.json()['key'] == f"{project['key']}-2"


def test_list_and_filter(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _make_project(api, h)
    api.post(
        f"/projects/{project['id']}/issues",
        headers=h,
        json={'type': 'story', 'summary': 'S'},
    )
    api.post(
        f"/projects/{project['id']}/issues",
        headers=h,
        json={'type': 'bug', 'summary': 'B'},
    )

    all_issues = api.get(f"/projects/{project['id']}/issues", headers=h).json()
    assert len(all_issues) == 2

    bugs = api.get(
        f"/projects/{project['id']}/issues", headers=h, params={'type': 'bug'}
    ).json()
    assert len(bugs) == 1 and bugs[0]['type'] == 'bug'


def test_get_update_delete(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _make_project(api, h)
    key = api.post(
        f"/projects/{project['id']}/issues",
        headers=h,
        json={'type': 'task', 'summary': 'À modifier'},
    ).json()['key']

    got = api.get(f"/issues/{key}", headers=h)
    assert got.status_code == 200
    assert 'description' in got.json()

    patched = api.patch(
        f"/issues/{key}",
        headers=h,
        json={'status': 'in_progress', 'priority': 'high'},
    )
    assert patched.status_code == 200
    assert patched.json()['status'] == 'in_progress'
    assert patched.json()['priority'] == 'high'

    assert api.delete(f"/issues/{key}", headers=h).status_code == 204
    assert api.get(f"/issues/{key}", headers=h).status_code == 404


def test_labels_flow(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _make_project(api, h)
    label = api.post(
        f"/projects/{project['id']}/labels",
        headers=h,
        json={'name': 'urgent', 'color': '#EF4444'},
    )
    assert label.status_code == 201, label.text
    label_id = label.json()['id']

    key = api.post(
        f"/projects/{project['id']}/issues",
        headers=h,
        json={'type': 'story', 'summary': 'Avec label', 'label_ids': [label_id]},
    ).json()['key']

    detail = api.get(f"/issues/{key}", headers=h).json()
    assert any(lbl['id'] == label_id for lbl in detail['labels'])


def test_epic_hierarchy(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _make_project(api, h)
    epic = api.post(
        f"/projects/{project['id']}/issues",
        headers=h,
        json={'type': 'epic', 'summary': 'Grande feature'},
    ).json()

    child = api.post(
        f"/projects/{project['id']}/issues",
        headers=h,
        json={'type': 'story', 'summary': 'Enfant', 'epic_id': epic['id']},
    )
    assert child.status_code == 201, child.text

    epic_detail = api.get(f"/issues/{epic['key']}", headers=h).json()
    assert epic_detail['progress'] is not None
    assert epic_detail['progress']['total'] == 1
    assert any(c['id'] == child.json()['id'] for c in epic_detail['children'])

    # Rattacher à un non-epic → 422.
    bad = api.post(
        f"/projects/{project['id']}/issues",
        headers=h,
        json={'type': 'task', 'summary': 'Bad', 'epic_id': child.json()['id']},
    )
    assert bad.status_code == 422


def test_project_viewer_cannot_create(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _make_project(api, h)
    viewer = _make_user(api)
    # Le lead ajoute le second user comme viewer projet.
    api.post(
        f"/projects/{project['id']}/members",
        headers=h,
        json={'email': viewer['email'], 'role': 'viewer'},
    )
    r = api.post(
        f"/projects/{project['id']}/issues",
        headers=viewer['auth_header'],
        json={'type': 'task', 'summary': 'Interdit'},
    )
    assert r.status_code == 403
