"""Projets (EPIC-04) — parcours end-to-end contre l'API réelle."""

from __future__ import annotations

import uuid

import httpx

from conftest import unique_email


def _random_key() -> str:
    """Clé valide unique : ^[A-Z][A-Z0-9]{1,4}$ (5 caractères)."""
    return ('T' + uuid.uuid4().hex[:4]).upper()


def _make_user(api: httpx.Client) -> dict:
    email = unique_email()
    password = 'password123'
    api.post(
        '/auth/register',
        json={'email': email, 'password': password, 'full_name': 'Membre'},
    )
    tokens = api.post(
        '/auth/login', json={'email': email, 'password': password}
    ).json()
    return {
        'email': email,
        'auth_header': {'Authorization': f"Bearer {tokens['access_token']}"},
    }


def test_create_project(api: httpx.Client, new_user: dict) -> None:
    key = _random_key()
    r = api.post(
        '/projects',
        headers=new_user['auth_header'],
        json={'name': 'Mon Projet', 'key': key, 'description': 'desc'},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body['key'] == key
    assert body['my_role'] == 'admin'
    assert body['member_count'] == 1


def test_list_returns_only_my_projects(api: httpx.Client, new_user: dict) -> None:
    key = _random_key()
    created = api.post(
        '/projects',
        headers=new_user['auth_header'],
        json={'name': 'Listable', 'key': key},
    ).json()

    mine = api.get('/projects', headers=new_user['auth_header'])
    assert mine.status_code == 200
    assert any(p['id'] == created['id'] for p in mine.json())

    # Un autre utilisateur ne voit pas ce projet.
    other = _make_user(api)
    other_list = api.get('/projects', headers=other['auth_header'])
    assert all(p['id'] != created['id'] for p in other_list.json())


def test_duplicate_key_conflict(api: httpx.Client, new_user: dict) -> None:
    key = _random_key()
    payload = {'name': 'A', 'key': key}
    assert (
        api.post('/projects', headers=new_user['auth_header'], json=payload).status_code
        == 201
    )
    assert (
        api.post('/projects', headers=new_user['auth_header'], json=payload).status_code
        == 409
    )


def test_invalid_key_rejected(api: httpx.Client, new_user: dict) -> None:
    r = api.post(
        '/projects',
        headers=new_user['auth_header'],
        json={'name': 'Bad', 'key': '1x'},  # ne commence pas par une lettre
    )
    assert r.status_code == 422


def test_non_member_cannot_access(api: httpx.Client, new_user: dict) -> None:
    created = api.post(
        '/projects',
        headers=new_user['auth_header'],
        json={'name': 'Privé', 'key': _random_key()},
    ).json()
    other = _make_user(api)
    r = api.get(f"/projects/{created['id']}", headers=other['auth_header'])
    assert r.status_code == 403


def test_add_member_and_detail(api: httpx.Client, new_user: dict) -> None:
    created = api.post(
        '/projects',
        headers=new_user['auth_header'],
        json={'name': 'Équipe', 'key': _random_key()},
    ).json()
    other = _make_user(api)

    add = api.post(
        f"/projects/{created['id']}/members",
        headers=new_user['auth_header'],
        json={'email': other['email'], 'role': 'member'},
    )
    assert add.status_code == 201, add.text

    detail = api.get(
        f"/projects/{created['id']}", headers=new_user['auth_header']
    ).json()
    assert detail['member_count'] == 2
    assert len(detail['members']) == 2

    # Le membre (rôle projet non-admin) ne peut pas modifier le projet.
    forbidden = api.patch(
        f"/projects/{created['id']}",
        headers=other['auth_header'],
        json={'name': 'Renommé'},
    )
    assert forbidden.status_code == 403


def test_archive_project(api: httpx.Client, new_user: dict) -> None:
    created = api.post(
        '/projects',
        headers=new_user['auth_header'],
        json={'name': 'À archiver', 'key': _random_key()},
    ).json()
    r = api.delete(
        f"/projects/{created['id']}", headers=new_user['auth_header']
    )
    assert r.status_code == 204
    # N'apparaît plus dans la liste par défaut.
    listed = api.get('/projects', headers=new_user['auth_header']).json()
    assert all(p['id'] != created['id'] for p in listed)
