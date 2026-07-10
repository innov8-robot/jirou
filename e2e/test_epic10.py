"""Recherche, activité, stats, vues sauvegardées, mes tickets (EPIC-10) — e2e."""

from __future__ import annotations

import uuid

import httpx

from conftest import unique_email


def _key() -> str:
    return ('T' + uuid.uuid4().hex[:4]).upper()


def _project(api, h, name='P') -> dict:
    return api.post('/projects', headers=h, json={'name': name, 'key': _key()}).json()


def _issue(api, h, pid, summary, itype='task', **extra) -> dict:
    return api.post(
        f'/projects/{pid}/issues',
        headers=h,
        json={'type': itype, 'summary': summary, **extra},
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
    header = {'Authorization': f'Bearer {tok}'}
    me = api.get('/auth/me', headers=header).json()
    return {'email': email, 'auth_header': header, 'id': me['id']}


# ---- Recherche (JIR-68) ----

def test_search_by_key_and_text(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h, 'Searchable')
    marker = f'zbx{uuid.uuid4().hex[:6]}'
    issue = _issue(api, h, project['id'], f'Titre {marker}')

    by_text = api.get('/search', headers=h, params={'q': marker}).json()
    assert any(i['key'] == issue['key'] for i in by_text['issues'])

    by_key = api.get('/search', headers=h, params={'q': issue['key']}).json()
    assert any(i['key'] == issue['key'] for i in by_key['issues'])


def test_search_excludes_foreign_projects(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h, 'Secret')
    marker = f'zsec{uuid.uuid4().hex[:6]}'
    _issue(api, h, project['id'], f'caché {marker}')
    other = _make_user(api)
    res = api.get('/search', headers=other['auth_header'], params={'q': marker}).json()
    assert res['issues'] == []


# ---- Activité (JIR-69) ----

def test_activity_created_and_updated(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    issue = _issue(api, h, _project(api, h)['id'], 'Suivi')
    api.patch(f"/issues/{issue['key']}", headers=h, json={'status': 'in_progress'})

    acts = api.get(f"/issues/{issue['key']}/activity", headers=h).json()
    assert any(a['action'] == 'created' for a in acts)
    assert any(
        a['action'] == 'updated' and a['field'] == 'status' for a in acts
    )


# ---- Stats (JIR-71) ----

def test_project_stats(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    _issue(api, h, project['id'], 'A', itype='bug')
    _issue(api, h, project['id'], 'B', itype='story')
    stats = api.get(f"/projects/{project['id']}/stats", headers=h).json()
    assert stats['total'] == 2
    assert stats['by_type']['bug'] == 1
    assert stats['by_status']['todo'] == 2
    assert len(stats['recent']) == 2


# ---- Mes tickets (JIR-72) ----

def test_my_issues(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    me = api.get('/auth/me', headers=h).json()
    project = _project(api, h)
    issue = _issue(api, h, project['id'], 'Pour moi')
    api.patch(f"/issues/{issue['key']}", headers=h, json={'assignee_id': me['id']})

    mine = api.get('/users/me/issues', headers=h).json()
    assert any(i['key'] == issue['key'] for i in mine)


# ---- Vues sauvegardées (JIR-70) ----

def test_saved_views_crud(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    payload = {'name': 'Bugs ouverts', 'filters': {'type': 'bug', 'status': 'todo'}}
    created = api.post(f"/projects/{project['id']}/views", headers=h, json=payload)
    assert created.status_code == 201, created.text

    lst = api.get(f"/projects/{project['id']}/views", headers=h).json()
    assert any(v['name'] == 'Bugs ouverts' for v in lst)

    # Doublon → 409
    assert (
        api.post(f"/projects/{project['id']}/views", headers=h, json=payload).status_code
        == 409
    )

    vid = created.json()['id']
    assert api.delete(f"/views/{vid}", headers=h).status_code == 204


def test_saved_views_isolated_per_user(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    api.post(
        f"/projects/{project['id']}/views",
        headers=h,
        json={'name': 'Mienne', 'filters': {}},
    )
    other = _make_user(api)
    # L'autre user est ajouté au projet mais ne voit pas la vue du premier.
    api.post(
        f"/projects/{project['id']}/members",
        headers=h,
        json={'email': other['email'], 'role': 'member'},
    )
    lst = api.get(
        f"/projects/{project['id']}/views", headers=other['auth_header']
    ).json()
    assert all(v['name'] != 'Mienne' for v in lst)
