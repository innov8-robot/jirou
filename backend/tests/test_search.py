"""Tests d'intégration de la RECHERCHE GLOBALE (EPIC-10, JIR-68).

Couvre la recherche par clé et par texte, l'isolation par appartenance projet
(on ne voit pas les projets/tickets d'un projet dont on n'est pas membre) et le
cas ``q`` vide.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

VALID_PASSWORD = "s3cretpwd"


def _register(client: TestClient, email: str, full_name: str = "User") -> dict:
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": VALID_PASSWORD, "full_name": full_name},
    ).json()


def _login(client: TestClient, email: str) -> str:
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": VALID_PASSWORD},
    ).json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(client: TestClient, email: str) -> str:
    _register(client, email)
    return _login(client, email)


def _create_project(client: TestClient, token: str, key: str, name: str | None = None) -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"name": name or f"Project {key}", "key": key},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_issue(client: TestClient, token: str, project_id: int, **fields: object) -> dict:
    payload = {"type": "task", "summary": "Do something", **fields}
    resp = client.post(f"/api/v1/projects/{project_id}/issues", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_search_by_key_and_text(client: TestClient) -> None:
    token = _make_user(client, "searcher@example.com")
    proj = _create_project(client, token, key="SRCH", name="Recherche App")
    issue = _create_issue(client, token, proj["id"], summary="Corriger la pagination du board")

    # Par clé (préfixe insensible à la casse).
    resp = client.get("/api/v1/search", params={"q": issue["key"]}, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    keys = [i["key"] for i in resp.json()["issues"]]
    assert issue["key"] in keys

    # Par texte du résumé.
    resp = client.get("/api/v1/search", params={"q": "pagination"}, headers=_auth(token))
    assert resp.status_code == 200
    keys = [i["key"] for i in resp.json()["issues"]]
    assert issue["key"] in keys

    # Par nom de projet.
    resp = client.get("/api/v1/search", params={"q": "Recherche"}, headers=_auth(token))
    assert resp.status_code == 200
    proj_ids = [p["id"] for p in resp.json()["projects"]]
    assert proj["id"] in proj_ids


def test_search_scoped_to_membership(client: TestClient) -> None:
    owner_token = _make_user(client, "owner@example.com")
    proj = _create_project(client, owner_token, key="PRIV", name="Projet Privé")
    issue = _create_issue(client, owner_token, proj["id"], summary="Secret pagination")

    # Un utilisateur non membre ne voit ni le projet ni ses tickets.
    outsider_token = _make_user(client, "outsider@example.com")
    resp = client.get("/api/v1/search", params={"q": "pagination"}, headers=_auth(outsider_token))
    assert resp.status_code == 200
    assert resp.json()["issues"] == []

    resp = client.get("/api/v1/search", params={"q": issue["key"]}, headers=_auth(outsider_token))
    assert resp.json()["issues"] == []

    resp = client.get("/api/v1/search", params={"q": "Privé"}, headers=_auth(outsider_token))
    assert resp.json()["projects"] == []


def test_search_empty_query_returns_empty(client: TestClient) -> None:
    token = _make_user(client, "empty@example.com")
    proj = _create_project(client, token, key="EMP")
    _create_issue(client, token, proj["id"], summary="Quelque chose")

    resp = client.get("/api/v1/search", params={"q": ""}, headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"issues": [], "projects": []}

    resp = client.get("/api/v1/search", params={"q": "   "}, headers=_auth(token))
    assert resp.json() == {"issues": [], "projects": []}
