"""Import CSV de tickets — end-to-end."""

from __future__ import annotations

import uuid

import httpx

from conftest import unique_email


def _key() -> str:
    return ('T' + uuid.uuid4().hex[:4]).upper()


def _project(api, h) -> dict:
    return api.post('/projects', headers=h, json={'name': 'Imp', 'key': _key()}).json()


def _make_user(api: httpx.Client) -> dict:
    email = unique_email()
    api.post(
        '/auth/register',
        json={'email': email, 'password': 'password123', 'full_name': 'U'},
    )
    tok = api.post(
        '/auth/login', json={'email': email, 'password': 'password123'}
    ).json()['access_token']
    return {'email': email, 'auth_header': {'Authorization': f'Bearer {tok}'}}


HEADER = 'type,summary,description,priority,story_points,status,labels,assignee_email,epic_key'


def test_import_epic_with_children(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    csv = (
        f'{HEADER}\n'
        'epic,Authentification,Gérer les comptes,high,,todo,auth,,\n'
        'story,Écran de connexion,,high,5,todo,auth;frontend,,Authentification\n'
        'task,Endpoint login,,medium,3,in_progress,backend,,Authentification\n'
    )
    r = api.post(
        f"/projects/{project['id']}/issues/import",
        headers=h,
        files={'file': ('import.csv', csv.encode(), 'text/csv')},
    )
    assert r.status_code == 200, r.text
    res = r.json()
    assert res['created'] == 3

    issues = {i['summary']: i for i in res['issues']}
    epic = issues['Authentification']
    child = issues['Écran de connexion']
    assert epic['type'] == 'epic'
    assert child['epic_id'] == epic['id']
    assert child['story_points'] == 5
    assert any(lbl['name'].lower() == 'frontend' for lbl in child['labels'])


def test_import_into_target_epic(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    epic = api.post(
        f"/projects/{project['id']}/issues",
        headers=h,
        json={'type': 'epic', 'summary': 'Sprint goal'},
    ).json()
    csv = f'{HEADER}\ntask,Tâche importée,,medium,,todo,,,\n'
    r = api.post(
        f"/projects/{project['id']}/issues/import",
        headers=h,
        files={'file': ('i.csv', csv.encode(), 'text/csv')},
        data={'epic_id': str(epic['id'])},
    )
    assert r.status_code == 200, r.text
    assert r.json()['issues'][0]['epic_id'] == epic['id']


def test_import_reports_invalid_rows(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    csv = (
        f'{HEADER}\n'
        'task,,,medium,,todo,,,\n'  # summary vide → erreur
        'task,Valide,,medium,,todo,,,\n'
    )
    r = api.post(
        f"/projects/{project['id']}/issues/import",
        headers=h,
        files={'file': ('i.csv', csv.encode(), 'text/csv')},
    )
    assert r.status_code == 200, r.text
    res = r.json()
    assert res['created'] == 1
    assert res['error_count'] >= 1


def test_import_viewer_forbidden(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    viewer = _make_user(api)
    api.post(
        f"/projects/{project['id']}/members",
        headers=h,
        json={'email': viewer['email'], 'role': 'viewer'},
    )
    csv = f'{HEADER}\ntask,X,,medium,,todo,,,\n'
    r = api.post(
        f"/projects/{project['id']}/issues/import",
        headers=viewer['auth_header'],
        files={'file': ('i.csv', csv.encode(), 'text/csv')},
    )
    assert r.status_code == 403
