"""Commentaires & mentions (EPIC-09) — end-to-end."""

from __future__ import annotations

import uuid

import httpx

from conftest import unique_email


def _key() -> str:
    return ('T' + uuid.uuid4().hex[:4]).upper()


def _project(api, h) -> dict:
    return api.post('/projects', headers=h, json={'name': 'C', 'key': _key()}).json()


def _issue(api, h, pid) -> dict:
    return api.post(
        f'/projects/{pid}/issues', headers=h, json={'type': 'task', 'summary': 'S'}
    ).json()


def _make_user(api: httpx.Client) -> dict:
    email = unique_email()
    api.post(
        '/auth/register',
        json={'email': email, 'password': 'password123', 'full_name': 'Membre M'},
    )
    tok = api.post(
        '/auth/login', json={'email': email, 'password': 'password123'}
    ).json()['access_token']
    header = {'Authorization': f'Bearer {tok}'}
    me = api.get('/auth/me', headers=header).json()
    return {'email': email, 'auth_header': header, 'id': me['id']}


def test_comment_crud_and_order(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    issue = _issue(api, h, _project(api, h)['id'])
    c1 = api.post(
        f"/issues/{issue['key']}/comments", headers=h, json={'body': '<p>un</p>'}
    )
    assert c1.status_code == 201, c1.text
    api.post(f"/issues/{issue['key']}/comments", headers=h, json={'body': '<p>deux</p>'})

    lst = api.get(f"/issues/{issue['key']}/comments", headers=h).json()
    assert [c['body'] for c in lst] == ['<p>un</p>', '<p>deux</p>']

    cid = c1.json()['id']
    assert (
        api.patch(f'/comments/{cid}', headers=h, json={'body': '<p>edit</p>'}).status_code
        == 200
    )
    assert api.delete(f'/comments/{cid}', headers=h).status_code == 204


def test_viewer_cannot_comment(api: httpx.Client, new_user: dict) -> None:
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
        f"/issues/{issue['key']}/comments",
        headers=viewer['auth_header'],
        json={'body': '<p>no</p>'},
    )
    assert r.status_code == 403


def test_mention_creates_notification(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    issue = _issue(api, h, project['id'])
    member = _make_user(api)
    api.post(
        f"/projects/{project['id']}/members",
        headers=h,
        json={'email': member['email'], 'role': 'member'},
    )
    api.post(
        f"/issues/{issue['key']}/comments",
        headers=h,
        json={'body': '<p>coucou</p>', 'mention_user_ids': [member['id']]},
    )
    notifs = api.get('/notifications', headers=member['auth_header']).json()
    assert any(n['type'] == 'mention' for n in notifs)
