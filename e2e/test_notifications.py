"""Notifications in-app (EPIC-09) — end-to-end."""

from __future__ import annotations

import uuid

import httpx

from conftest import unique_email


def _key() -> str:
    return ('T' + uuid.uuid4().hex[:4]).upper()


def _project(api, h) -> dict:
    return api.post('/projects', headers=h, json={'name': 'N', 'key': _key()}).json()


def _make_user(api: httpx.Client) -> dict:
    email = unique_email()
    api.post(
        '/auth/register',
        json={'email': email, 'password': 'password123', 'full_name': 'Assigné A'},
    )
    tok = api.post(
        '/auth/login', json={'email': email, 'password': 'password123'}
    ).json()['access_token']
    header = {'Authorization': f'Bearer {tok}'}
    me = api.get('/auth/me', headers=header).json()
    return {'email': email, 'auth_header': header, 'id': me['id']}


def test_assignment_notification_flow(api: httpx.Client, new_user: dict) -> None:
    owner = new_user['auth_header']
    project = _project(api, owner)
    member = _make_user(api)
    api.post(
        f"/projects/{project['id']}/members",
        headers=owner,
        json={'email': member['email'], 'role': 'member'},
    )
    issue = api.post(
        f"/projects/{project['id']}/issues",
        headers=owner,
        json={'type': 'task', 'summary': 'Assign me'},
    ).json()

    # L'owner assigne le ticket au membre → notification pour le membre.
    api.patch(
        f"/issues/{issue['key']}",
        headers=owner,
        json={'assignee_id': member['id']},
    )

    mh = member['auth_header']
    notifs = api.get('/notifications', headers=mh).json()
    assign = [n for n in notifs if n['type'] == 'assignment']
    assert assign, notifs

    count = api.get('/notifications/unread-count', headers=mh).json()['count']
    assert count >= 1

    # Marquer lu.
    api.patch(f"/notifications/{assign[0]['id']}/read", headers=mh)
    api.post('/notifications/read-all', headers=mh)
    assert api.get('/notifications/unread-count', headers=mh).json()['count'] == 0


def test_only_own_notifications(api: httpx.Client, new_user: dict) -> None:
    # Un nouvel utilisateur sans activité n'a aucune notification.
    other = _make_user(api)
    notifs = api.get('/notifications', headers=other['auth_header']).json()
    assert notifs == []
