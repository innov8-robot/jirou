"""Export CSV des tickets d'un projet — end-to-end."""

from __future__ import annotations

import csv
import io
import uuid

import httpx

from conftest import unique_email


def _key() -> str:
    return ('X' + uuid.uuid4().hex[:4]).upper()


def _project(api, h) -> dict:
    return api.post('/projects', headers=h, json={'name': 'Exp', 'key': _key()}).json()


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


def _rows(response: httpx.Response) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))


def test_export_returns_csv_of_project_issues(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    epic = api.post(
        f"/projects/{project['id']}/issues",
        headers=h,
        json={'type': 'epic', 'summary': 'Socle technique'},
    ).json()
    api.post(
        f"/projects/{project['id']}/issues",
        headers=h,
        json={
            'type': 'story',
            'summary': 'Pipeline CI',
            'priority': 'high',
            'story_points': 3,
            'epic_id': epic['id'],
        },
    )

    r = api.get(f"/projects/{project['id']}/issues/export", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers['content-type'].startswith('text/csv')
    assert f"{project['key']}-tickets-" in r.headers['content-disposition']

    rows = {row['summary']: row for row in _rows(r)}
    assert set(rows) == {'Socle technique', 'Pipeline CI'}
    story = rows['Pipeline CI']
    assert story['type'] == 'story'
    assert story['priority'] == 'high'
    assert story['story_points'] == '3'
    assert story['epic_key'] == epic['key']


def test_export_respects_filters(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    for body in (
        {'type': 'bug', 'summary': 'Un bug'},
        {'type': 'task', 'summary': 'Une tâche'},
    ):
        api.post(f"/projects/{project['id']}/issues", headers=h, json=body)

    r = api.get(
        f"/projects/{project['id']}/issues/export", headers=h, params={'type': 'bug'}
    )
    assert r.status_code == 200
    assert [row['summary'] for row in _rows(r)] == ['Un bug']


def test_exported_csv_is_reimportable(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    api.post(
        f"/projects/{project['id']}/issues",
        headers=h,
        json={'type': 'task', 'summary': 'À dupliquer', 'priority': 'low'},
    )
    exported = api.get(f"/projects/{project['id']}/issues/export", headers=h)
    assert exported.status_code == 200

    r = api.post(
        f"/projects/{project['id']}/issues/import",
        headers=h,
        files={'file': ('export.csv', exported.content, 'text/csv')},
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert result['created'] == 1
    assert result['error_count'] == 0, result['errors']
    assert result['issues'][0]['summary'] == 'À dupliquer'
    assert result['issues'][0]['priority'] == 'low'


def test_export_allowed_for_viewer(api: httpx.Client, new_user: dict) -> None:
    """L'export est en lecture seule : un viewer y a droit (l'import non)."""
    h = new_user['auth_header']
    project = _project(api, h)
    viewer = _make_user(api)
    api.post(
        f"/projects/{project['id']}/members",
        headers=h,
        json={'email': viewer['email'], 'role': 'viewer'},
    )
    r = api.get(
        f"/projects/{project['id']}/issues/export", headers=viewer['auth_header']
    )
    assert r.status_code == 200


def test_export_forbidden_for_non_member(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    outsider = _make_user(api)
    r = api.get(
        f"/projects/{project['id']}/issues/export", headers=outsider['auth_header']
    )
    assert r.status_code == 403
