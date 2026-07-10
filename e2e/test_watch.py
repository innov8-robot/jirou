"""Veille (graphe R&D) — end-to-end."""

from __future__ import annotations

import httpx

from conftest import unique_email


def _make_user(api: httpx.Client) -> dict:
    email = unique_email()
    api.post(
        '/auth/register',
        json={'email': email, 'password': 'password123', 'full_name': 'U'},
    )
    tok = api.post(
        '/auth/login', json={'email': email, 'password': 'password123'}
    ).json()['access_token']
    return {'auth_header': {'Authorization': f'Bearer {tok}'}}


def test_node_tree_crud(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    root = api.post(
        '/watch/nodes', headers=h, json={'title': 'Mocap suit'}
    )
    assert root.status_code == 201, root.text
    root_id = root.json()['id']
    child = api.post(
        '/watch/nodes',
        headers=h,
        json={'title': 'IMU', 'parent_id': root_id, 'status': 'to_test'},
    )
    assert child.status_code == 201
    child_id = child.json()['id']

    nodes = api.get('/watch/nodes', headers=h).json()
    ids = {n['id'] for n in nodes}
    assert root_id in ids and child_id in ids
    assert any(n['id'] == child_id and n['parent_id'] == root_id for n in nodes)

    # Patch statut + position.
    p = api.patch(
        f'/watch/nodes/{child_id}',
        headers=h,
        json={'status': 'promising', 'pos_x': 120, 'pos_y': 240},
    )
    assert p.status_code == 200
    assert p.json()['status'] == 'promising'


def test_cycle_prevention(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    a = api.post('/watch/nodes', headers=h, json={'title': 'A'}).json()
    b = api.post(
        '/watch/nodes', headers=h, json={'title': 'B', 'parent_id': a['id']}
    ).json()
    # Rendre A enfant de B (son descendant) → cycle → 422.
    r = api.patch(f"/watch/nodes/{a['id']}", headers=h, json={'parent_id': b['id']})
    assert r.status_code == 422


def test_media_link_and_upload(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    node = api.post('/watch/nodes', headers=h, json={'title': 'Solution X'}).json()

    link = api.post(
        f"/watch/nodes/{node['id']}/media/link",
        headers=h,
        json={'url': 'https://youtu.be/dQw4w9WgXcQ', 'title': 'Démo'},
    )
    assert link.status_code == 201, link.text
    assert link.json()['kind'] == 'link'

    up = api.post(
        f"/watch/nodes/{node['id']}/media",
        headers=h,
        files={'file': ('img.png', b'\x89PNG\r\n\x1a\n fake', 'image/png')},
    )
    assert up.status_code == 201, up.text
    assert up.json()['kind'] == 'image'
    dl = api.get(f"/watch/media/{up.json()['id']}/download", headers=h)
    assert dl.status_code == 200

    detail = api.get(f"/watch/nodes/{node['id']}", headers=h).json()
    assert len(detail['media']) == 2


def test_comments(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    node = api.post('/watch/nodes', headers=h, json={'title': 'N'}).json()
    c = api.post(
        f"/watch/nodes/{node['id']}/comments", headers=h, json={'body': 'Intéressant'}
    )
    assert c.status_code == 201
    lst = api.get(f"/watch/nodes/{node['id']}/comments", headers=h).json()
    assert any(x['body'] == 'Intéressant' for x in lst)
    assert api.delete(f"/watch/comments/{c.json()['id']}", headers=h).status_code == 204


def test_delete_cascade_and_permission(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    a = api.post('/watch/nodes', headers=h, json={'title': 'Parent'}).json()
    b = api.post(
        '/watch/nodes', headers=h, json={'title': 'Enfant', 'parent_id': a['id']}
    ).json()

    # Un autre utilisateur ne peut pas supprimer le nœud d'autrui.
    other = _make_user(api)
    assert (
        api.delete(f"/watch/nodes/{a['id']}", headers=other['auth_header']).status_code
        == 403
    )

    # Le créateur supprime → cascade sur l'enfant.
    assert api.delete(f"/watch/nodes/{a['id']}", headers=h).status_code == 204
    nodes = api.get('/watch/nodes', headers=h).json()
    ids = {n['id'] for n in nodes}
    assert a['id'] not in ids and b['id'] not in ids
