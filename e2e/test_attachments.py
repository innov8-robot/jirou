"""Pièces jointes (EPIC-09) — end-to-end."""

from __future__ import annotations

import uuid

import httpx

from conftest import unique_email


def _key() -> str:
    return ('T' + uuid.uuid4().hex[:4]).upper()


def _project(api, h) -> dict:
    return api.post('/projects', headers=h, json={'name': 'A', 'key': _key()}).json()


def _issue(api, h, pid) -> dict:
    return api.post(
        f'/projects/{pid}/issues', headers=h, json={'type': 'task', 'summary': 'S'}
    ).json()


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


def test_upload_download_delete(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    issue = _issue(api, h, _project(api, h)['id'])
    content = b'hello jirou attachment'

    up = api.post(
        f"/issues/{issue['key']}/attachments",
        headers=h,
        files={'file': ('note.txt', content, 'text/plain')},
    )
    assert up.status_code == 201, up.text
    att = up.json()
    assert att['filename'] == 'note.txt'
    assert att['size'] == len(content)

    lst = api.get(f"/issues/{issue['key']}/attachments", headers=h).json()
    assert any(a['id'] == att['id'] for a in lst)

    dl = api.get(f"/attachments/{att['id']}/download", headers=h)
    assert dl.status_code == 200
    assert dl.content == content

    assert api.delete(f"/attachments/{att['id']}", headers=h).status_code == 204


def test_viewer_cannot_upload(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    issue = _issue(api, h, project['id'])
    viewer = _make_user(api)
    api.post(
        f"/projects/{project['id']}/members",
        headers=h,
        json={'email': viewer['email'], 'role': 'viewer'},
    )
    r = api.post(
        f"/issues/{issue['key']}/attachments",
        headers=viewer['auth_header'],
        files={'file': ('x.txt', b'x', 'text/plain')},
    )
    assert r.status_code == 403
