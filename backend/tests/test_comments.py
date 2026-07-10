"""Tests d'intégration des COMMENTAIRES (EPIC-09, JIR-62/64).

Couvre le CRUD, l'ordre chronologique, l'interdiction faite au viewer de
commenter, la réservation de l'édition/suppression, et la création de
notifications de mention (pour le mentionné, jamais pour l'auteur ni un
non-membre).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

VALID_PASSWORD = "s3cretpwd"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _register(client: TestClient, email: str, full_name: str = "User") -> dict:
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": VALID_PASSWORD, "full_name": full_name},
    ).json()


def _login(client: TestClient, email: str, password: str = VALID_PASSWORD) -> str:
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(client: TestClient, email: str, full_name: str = "User") -> tuple[dict, str]:
    profile = _register(client, email, full_name)
    return profile, _login(client, email)


def _create_project(client: TestClient, token: str, key: str = "DEMO") -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"name": f"Project {key}", "key": key},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _add_member(client: TestClient, token: str, project_id: int, email: str, role: str) -> None:
    resp = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": email, "role": role},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text


def _create_issue(client: TestClient, token: str, project_id: int, **fields: object) -> dict:
    payload = {"type": "task", "summary": "Do something", **fields}
    resp = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json=payload,
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _post_comment(
    client: TestClient, token: str, key: str, body: str, mentions: list[int] | None = None
) -> object:
    payload: dict = {"body": body}
    if mentions is not None:
        payload["mention_user_ids"] = mentions
    return client.post(f"/api/v1/issues/{key}/comments", json=payload, headers=_auth(token))


# --------------------------------------------------------------------------- #
# CRUD & ordre chronologique
# --------------------------------------------------------------------------- #
def test_create_and_list_comments_chronological(client: TestClient) -> None:
    profile, token = _make_user(client, "author@example.com", "Author")
    proj = _create_project(client, token, key="CMT")
    issue = _create_issue(client, token, proj["id"])

    r1 = _post_comment(client, token, issue["key"], "Premier")
    assert r1.status_code == 201, r1.text
    first = r1.json()
    assert first["issue_id"] == issue["id"]
    assert first["author"]["id"] == profile["id"]
    assert first["body"] == "Premier"

    _post_comment(client, token, issue["key"], "Deuxième")
    _post_comment(client, token, issue["key"], "Troisième")

    resp = client.get(f"/api/v1/issues/{issue['key']}/comments", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    bodies = [c["body"] for c in resp.json()]
    assert bodies == ["Premier", "Deuxième", "Troisième"]


def test_viewer_cannot_comment(client: TestClient) -> None:
    _, lead_token = _make_user(client, "lead@example.com")
    _make_user(client, "viewer@example.com")
    proj = _create_project(client, lead_token, key="VWR")
    _add_member(client, lead_token, proj["id"], "viewer@example.com", "viewer")
    issue = _create_issue(client, lead_token, proj["id"])

    viewer_token = _login(client, "viewer@example.com")
    resp = _post_comment(client, viewer_token, issue["key"], "Nope")
    assert resp.status_code == 403, resp.text


def test_comment_not_found(client: TestClient) -> None:
    _, token = _make_user(client, "nf@example.com")
    resp = client.patch("/api/v1/comments/999999", json={"body": "x"}, headers=_auth(token))
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------------- #
# Édition / suppression réservées
# --------------------------------------------------------------------------- #
def test_update_comment_author_only(client: TestClient) -> None:
    _, lead_token = _make_user(client, "boss@example.com")
    other_profile, _ = _make_user(client, "mate@example.com")
    proj = _create_project(client, lead_token, key="EDT")
    _add_member(client, lead_token, proj["id"], "mate@example.com", "member")
    issue = _create_issue(client, lead_token, proj["id"])

    comment = _post_comment(client, lead_token, issue["key"], "Original").json()
    mate_token = _login(client, "mate@example.com")

    # Un autre membre ne peut pas éditer.
    forbidden = client.patch(
        f"/api/v1/comments/{comment['id']}",
        json={"body": "Hacked"},
        headers=_auth(mate_token),
    )
    assert forbidden.status_code == 403, forbidden.text

    # L'auteur peut éditer.
    ok = client.patch(
        f"/api/v1/comments/{comment['id']}",
        json={"body": "Édité"},
        headers=_auth(lead_token),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["body"] == "Édité"


def test_delete_comment_permissions(client: TestClient) -> None:
    _, lead_token = _make_user(client, "chief@example.com")
    _make_user(client, "author2@example.com")
    _make_user(client, "bystander@example.com")
    proj = _create_project(client, lead_token, key="DEL")
    _add_member(client, lead_token, proj["id"], "author2@example.com", "member")
    _add_member(client, lead_token, proj["id"], "bystander@example.com", "member")
    issue = _create_issue(client, lead_token, proj["id"])

    author_token = _login(client, "author2@example.com")
    bystander_token = _login(client, "bystander@example.com")

    # Un autre membre simple ne peut pas supprimer le commentaire d'autrui.
    c1 = _post_comment(client, author_token, issue["key"], "A supprimer 1").json()
    forbidden = client.delete(f"/api/v1/comments/{c1['id']}", headers=_auth(bystander_token))
    assert forbidden.status_code == 403, forbidden.text

    # L'auteur peut supprimer le sien.
    ok = client.delete(f"/api/v1/comments/{c1['id']}", headers=_auth(author_token))
    assert ok.status_code == 204, ok.text

    # Le lead du projet peut supprimer le commentaire d'un autre.
    c2 = _post_comment(client, author_token, issue["key"], "A supprimer 2").json()
    lead_ok = client.delete(f"/api/v1/comments/{c2['id']}", headers=_auth(lead_token))
    assert lead_ok.status_code == 204, lead_ok.text


# --------------------------------------------------------------------------- #
# Mentions -> notifications
# --------------------------------------------------------------------------- #
def _unread_count(client: TestClient, token: str) -> int:
    resp = client.get("/api/v1/notifications/unread-count", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["count"]


def test_mention_creates_notification_for_member_only(client: TestClient) -> None:
    author_profile, author_token = _make_user(client, "writer@example.com", "Writer")
    mentioned_profile, _ = _make_user(client, "mentioned@example.com", "Mentioned")
    outsider_profile, _ = _make_user(client, "outsider@example.com", "Outsider")
    proj = _create_project(client, author_token, key="MEN")
    _add_member(client, author_token, proj["id"], "mentioned@example.com", "member")
    issue = _create_issue(client, author_token, proj["id"])

    # Mentionne : le membre, l'auteur lui-même et un non-membre.
    resp = _post_comment(
        client,
        author_token,
        issue["key"],
        "coucou @mentioned",
        mentions=[
            mentioned_profile["id"],
            author_profile["id"],
            outsider_profile["id"],
        ],
    )
    assert resp.status_code == 201, resp.text

    mentioned_token = _login(client, "mentioned@example.com")
    notifs = client.get("/api/v1/notifications", headers=_auth(mentioned_token)).json()
    assert len(notifs) == 1
    notif = notifs[0]
    assert notif["type"] == "mention"
    assert notif["actor"]["id"] == author_profile["id"]
    assert notif["issue_key"] == issue["key"]
    assert notif["project_id"] == proj["id"]
    assert notif["is_read"] is False
    assert issue["key"] in notif["message"]

    # L'auteur ne se notifie pas lui-même.
    assert _unread_count(client, author_token) == 0
    # Le non-membre n'est pas notifié.
    outsider_token = _login(client, "outsider@example.com")
    assert _unread_count(client, outsider_token) == 0
