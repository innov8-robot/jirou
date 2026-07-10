"""Documents généraux + liste globale — end-to-end."""

from __future__ import annotations

import uuid

import httpx

from conftest import unique_email


def _key() -> str:
    return ('T' + uuid.uuid4().hex[:4]).upper()


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


def test_create_general_document(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    r = api.post('/documents', headers=h, json={'title': 'Général', 'content': '# G'})
    assert r.status_code == 201, r.text
    assert r.json()['project_id'] is None


def test_global_list_scope(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    # doc général + doc dans un projet du user
    gen = api.post('/documents', headers=h, json={'title': f'Gen {uuid.uuid4().hex[:6]}'}).json()
    project = api.post('/projects', headers=h, json={'name': 'P', 'key': _key()}).json()
    proj_doc = api.post(
        f"/projects/{project['id']}/documents", headers=h, json={'title': 'Doc projet'}
    ).json()

    mine = api.get('/documents', headers=h).json()
    ids = {d['id'] for d in mine}
    assert gen['id'] in ids and proj_doc['id'] in ids
    # le doc projet porte bien son projet, le général non
    assert any(d['id'] == proj_doc['id'] and d['project'] for d in mine)
    assert any(d['id'] == gen['id'] and d['project'] is None for d in mine)

    # un autre user voit le doc général mais PAS le doc du projet (non membre)
    other = _make_user(api)
    theirs = api.get('/documents', headers=other['auth_header']).json()
    tids = {d['id'] for d in theirs}
    assert gen['id'] in tids
    assert proj_doc['id'] not in tids


def test_general_doc_permissions(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    gen = api.post('/documents', headers=h, json={'title': 'Partagé'}).json()
    other = _make_user(api)

    # lecture par un autre user connecté : OK
    assert api.get(f"/documents/{gen['id']}", headers=other['auth_header']).status_code == 200
    # édition/suppression par un autre user : interdit
    assert (
        api.patch(
            f"/documents/{gen['id']}", headers=other['auth_header'], json={'title': 'X'}
        ).status_code
        == 403
    )
    assert (
        api.delete(
            f"/documents/{gen['id']}", headers=other['auth_header']
        ).status_code
        == 403
    )
    # par l'auteur : OK
    assert (
        api.patch(f"/documents/{gen['id']}", headers=h, json={'title': 'Y'}).status_code
        == 200
    )
