"""Timeline & dépendances (EPIC-08) — end-to-end contre l'API réelle."""

from __future__ import annotations

import uuid

import httpx

from conftest import unique_email


def _key() -> str:
    return ('T' + uuid.uuid4().hex[:4]).upper()


def _project(api: httpx.Client, header: dict) -> dict:
    return api.post(
        '/projects', headers=header, json={'name': 'TL', 'key': _key()}
    ).json()


def _issue(api, header, project_id, itype, summary, **extra) -> dict:
    return api.post(
        f'/projects/{project_id}/issues',
        headers=header,
        json={'type': itype, 'summary': summary, **extra},
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
    return {'auth_header': {'Authorization': f"Bearer {tokens['access_token']}"}}


def test_timeline_epics_children_progress(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    epic = _issue(
        api, h, project['id'], 'epic', 'Grand Epic',
        start_date='2026-07-01', due_date='2026-07-31',
    )
    c1 = _issue(api, h, project['id'], 'story', 'Enfant 1', epic_id=epic['id'])
    _issue(api, h, project['id'], 'task', 'Enfant 2', epic_id=epic['id'])
    api.patch(f"/issues/{c1['key']}", headers=h, json={'status': 'done'})

    tl = api.get(f"/projects/{project['id']}/timeline", headers=h)
    assert tl.status_code == 200, tl.text
    body = tl.json()
    entry = next(e for e in body['epics'] if e['epic']['id'] == epic['id'])
    assert entry['progress'] == {'done': 1, 'total': 2}
    assert len(entry['children']) == 2


def test_timeline_forbidden_for_non_member(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    other = _make_user(api)
    r = api.get(
        f"/projects/{project['id']}/timeline", headers=other['auth_header']
    )
    assert r.status_code == 403


def test_dependency_create_and_detail(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    a = _issue(api, h, project['id'], 'epic', 'A',
               start_date='2026-07-01', due_date='2026-07-10')
    b = _issue(api, h, project['id'], 'epic', 'B',
               start_date='2026-07-11', due_date='2026-07-20')

    dep = api.post(
        f"/issues/{a['key']}/dependencies",
        headers=h,
        json={'target_key': b['key']},
    )
    assert dep.status_code == 201, dep.text

    # A bloque B → dans A: outward ; dans B: inward.
    da = api.get(f"/issues/{a['key']}", headers=h).json()
    assert any(
        d['direction'] == 'outward' and d['issue']['key'] == b['key']
        for d in da['dependencies']
    )
    db = api.get(f"/issues/{b['key']}", headers=h).json()
    assert any(
        d['direction'] == 'inward' and d['issue']['key'] == a['key']
        for d in db['dependencies']
    )

    # Présente dans la timeline (epic↔epic).
    tl = api.get(f"/projects/{project['id']}/timeline", headers=h).json()
    assert {'from_key': a['key'], 'to_key': b['key']} in tl['dependencies']


def test_dependency_validations(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    a = _issue(api, h, project['id'], 'task', 'A')
    b = _issue(api, h, project['id'], 'task', 'B')

    # self → 422
    assert (
        api.post(
            f"/issues/{a['key']}/dependencies",
            headers=h,
            json={'target_key': a['key']},
        ).status_code
        == 422
    )
    # ok
    d = api.post(
        f"/issues/{a['key']}/dependencies", headers=h, json={'target_key': b['key']}
    )
    assert d.status_code == 201
    # doublon → 409
    assert (
        api.post(
            f"/issues/{a['key']}/dependencies",
            headers=h,
            json={'target_key': b['key']},
        ).status_code
        == 409
    )
    # target autre projet → 422
    other_project = _project(api, h)
    x = _issue(api, h, other_project['id'], 'task', 'X')
    assert (
        api.post(
            f"/issues/{a['key']}/dependencies",
            headers=h,
            json={'target_key': x['key']},
        ).status_code
        == 422
    )


def test_dependency_delete(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    project = _project(api, h)
    a = _issue(api, h, project['id'], 'task', 'A')
    b = _issue(api, h, project['id'], 'task', 'B')
    dep = api.post(
        f"/issues/{a['key']}/dependencies", headers=h, json={'target_key': b['key']}
    ).json()
    dep_id = dep['id']
    assert (
        api.delete(
            f"/issues/{a['key']}/dependencies/{dep_id}", headers=h
        ).status_code
        == 204
    )
    da = api.get(f"/issues/{a['key']}", headers=h).json()
    assert da['dependencies'] == []
