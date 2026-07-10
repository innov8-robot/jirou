"""Documentation projet (pages Markdown) — end-to-end."""

from __future__ import annotations

import uuid

import httpx

from conftest import unique_email


def _key() -> str:
    return ('T' + uuid.uuid4().hex[:4]).upper()


def _project(api, h) -> dict:
    return api.post('/projects', headers=h, json={'name': 'Doc', 'key': _key()}).json()


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


def test_document_crud(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)

    created = api.post(
        f"/projects/{project['id']}/documents",
        headers=h,
        json={'title': 'Guide', 'content': '# Titre\n\nContenu **markdown**.'},
    )
    assert created.status_code == 201, created.text
    doc_id = created.json()['id']

    # Liste = résumés (sans contenu).
    lst = api.get(f"/projects/{project['id']}/documents", headers=h).json()
    assert any(d['id'] == doc_id and 'content' not in d for d in lst)

    # Détail = avec contenu.
    detail = api.get(f"/documents/{doc_id}", headers=h).json()
    assert detail['content'].startswith('# Titre')

    # Patch.
    upd = api.patch(
        f"/documents/{doc_id}", headers=h, json={'content': '# Modifié'}
    )
    assert upd.status_code == 200
    assert upd.json()['content'] == '# Modifié'

    # Delete.
    assert api.delete(f"/documents/{doc_id}", headers=h).status_code == 204
    assert api.get(f"/documents/{doc_id}", headers=h).status_code == 404


def test_viewer_cannot_create_document(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    viewer = _make_user(api)
    api.post(
        f"/projects/{project['id']}/members",
        headers=h,
        json={'email': viewer['email'], 'role': 'viewer'},
    )
    r = api.post(
        f"/projects/{project['id']}/documents",
        headers=viewer['auth_header'],
        json={'title': 'X'},
    )
    assert r.status_code == 403


def test_non_member_cannot_list_documents(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    other = _make_user(api)
    r = api.get(
        f"/projects/{project['id']}/documents", headers=other['auth_header']
    )
    assert r.status_code == 403
