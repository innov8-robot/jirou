"""Tests d'intégration du domaine VEILLE (arbre/graphe de connaissances R&D).

Couvre les nœuds (création racine/enfant, liste à plat, patch, détection de
cycle, suppression cascade et permissions), les médias (upload image, lien
externe, téléchargement, suppression, dépassement de taille) et les commentaires
(CRUD + permissions).

Les fichiers sont écrits dans un dossier temporaire (``UPLOAD_DIR`` surchargé)
pour ne pas polluer le dépôt.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings

VALID_PASSWORD = "s3cretpwd"


@pytest.fixture(autouse=True)
def _tmp_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirige le stockage des médias de veille vers un dossier temporaire."""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))


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


def _create_node(client: TestClient, token: str, **body: object) -> dict:
    body.setdefault("title", "Racine")
    resp = client.post("/api/v1/watch/nodes", json=body, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _upload_media(
    client: TestClient,
    token: str,
    node_id: int,
    *,
    name: str = "pic.png",
    content: bytes = b"\x89PNG\r\n\x1a\n binary",
    content_type: str = "image/png",
) -> object:
    return client.post(
        f"/api/v1/watch/nodes/{node_id}/media",
        files={"file": (name, content, content_type)},
        headers=_auth(token),
    )


# --------------------------------------------------------------------------- #
# Nœuds
# --------------------------------------------------------------------------- #
def test_create_root_and_child_node(client: TestClient) -> None:
    profile, token = _make_user(client, "w1@example.com", "Chercheur")
    root = _create_node(client, token, title="Racine", note="# Idée", status="to_test")
    assert root["parent_id"] is None
    assert root["title"] == "Racine"
    assert root["note"] == "# Idée"
    assert root["status"] == "to_test"
    # Défaut : ``theme`` quand ``type`` n'est pas fourni.
    assert root["type"] == "theme"
    assert root["created_by"]["id"] == profile["id"]
    assert root["media"] == []

    child = _create_node(client, token, title="Enfant", parent_id=root["id"], pos_x=10, pos_y=20)
    assert child["parent_id"] == root["id"]
    assert child["pos_x"] == 10
    assert child["pos_y"] == 20


def test_node_type_explicit_and_patch(client: TestClient) -> None:
    _, token = _make_user(client, "wtype@example.com")
    # Type explicite à la création.
    node = _create_node(client, token, title="Solution", type="solution")
    assert node["type"] == "solution"

    # Patch du type.
    resp = client.patch(
        f"/api/v1/watch/nodes/{node['id']}",
        json={"type": "techno"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["type"] == "techno"


def test_list_nodes_returns_flat_tree(client: TestClient) -> None:
    _, token = _make_user(client, "w2@example.com")
    root = _create_node(client, token, title="R")
    child = _create_node(client, token, title="C", parent_id=root["id"])
    _upload_media(client, token, child["id"])
    client.post(
        f"/api/v1/watch/nodes/{root['id']}/comments",
        json={"body": "hello"},
        headers=_auth(token),
    )

    resp = client.get("/api/v1/watch/nodes", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    nodes = {n["id"]: n for n in resp.json()}
    assert set(nodes) == {root["id"], child["id"]}
    assert nodes[root["id"]]["parent_id"] is None
    assert nodes[child["id"]]["parent_id"] == root["id"]
    assert nodes[child["id"]]["media_count"] == 1
    assert nodes[root["id"]]["comment_count"] == 1
    # Chaque résumé porte ``type`` (défaut ``theme``) et ``preview``.
    assert nodes[root["id"]]["type"] == "theme"
    assert nodes[child["id"]]["type"] == "theme"
    # Le nœud sans média n'a pas d'aperçu.
    assert nodes[root["id"]]["preview"] is None


def test_list_nodes_preview(client: TestClient) -> None:
    _, token = _make_user(client, "wprev@example.com")
    img_node = _create_node(client, token, title="Image")
    link_node = _create_node(client, token, title="Lien")
    empty_node = _create_node(client, token, title="Vide")

    media = _upload_media(client, token, img_node["id"]).json()
    client.post(
        f"/api/v1/watch/nodes/{link_node['id']}/media/link",
        json={"url": "https://youtube.com/watch?v=xyz"},
        headers=_auth(token),
    )

    nodes = {n["id"]: n for n in client.get("/api/v1/watch/nodes", headers=_auth(token)).json()}

    # Aperçu d'un upload image : kind image, download_url non nul, url nul.
    img_preview = nodes[img_node["id"]]["preview"]
    assert img_preview is not None
    assert img_preview["media_id"] == media["id"]
    assert img_preview["kind"] == "image"
    assert img_preview["download_url"] == f"/api/v1/watch/media/{media['id']}/download"
    assert img_preview["url"] is None
    assert img_preview["content_type"].startswith("image/")

    # Aperçu d'un lien : kind link, url non nul, download_url nul.
    link_preview = nodes[link_node["id"]]["preview"]
    assert link_preview is not None
    assert link_preview["kind"] == "link"
    assert link_preview["url"] == "https://youtube.com/watch?v=xyz"
    assert link_preview["download_url"] is None

    # Aucun média -> pas d'aperçu.
    assert nodes[empty_node["id"]]["preview"] is None


def test_patch_node(client: TestClient) -> None:
    _, token = _make_user(client, "w3@example.com")
    root = _create_node(client, token, title="R")
    other = _create_node(client, token, title="O")

    resp = client.patch(
        f"/api/v1/watch/nodes/{root['id']}",
        json={"title": "R2", "status": "promising", "pos_x": 5, "parent_id": other["id"]},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "R2"
    assert body["status"] == "promising"
    assert body["pos_x"] == 5
    assert body["parent_id"] == other["id"]


def test_patch_node_cycle_detection(client: TestClient) -> None:
    _, token = _make_user(client, "w4@example.com")
    root = _create_node(client, token, title="R")
    child = _create_node(client, token, title="C", parent_id=root["id"])
    grandchild = _create_node(client, token, title="G", parent_id=child["id"])

    # parent = soi-même
    resp = client.patch(
        f"/api/v1/watch/nodes/{root['id']}",
        json={"parent_id": root["id"]},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text

    # parent = descendant
    resp = client.patch(
        f"/api/v1/watch/nodes/{root['id']}",
        json={"parent_id": grandchild["id"]},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text


def test_delete_node_cascade(client: TestClient) -> None:
    _, token = _make_user(client, "w5@example.com")
    root = _create_node(client, token, title="R")
    child = _create_node(client, token, title="C", parent_id=root["id"])
    grandchild = _create_node(client, token, title="G", parent_id=child["id"])

    resp = client.delete(f"/api/v1/watch/nodes/{root['id']}", headers=_auth(token))
    assert resp.status_code == 204, resp.text

    listing = client.get("/api/v1/watch/nodes", headers=_auth(token)).json()
    remaining = {n["id"] for n in listing}
    assert child["id"] not in remaining
    assert grandchild["id"] not in remaining


def test_delete_node_permissions(client: TestClient, admin_token: str) -> None:
    _, creator_token = _make_user(client, "creator@example.com")
    _, other_token = _make_user(client, "otherw@example.com")
    node = _create_node(client, creator_token, title="R")

    # Non-créateur non-admin -> 403
    forbidden = client.delete(f"/api/v1/watch/nodes/{node['id']}", headers=_auth(other_token))
    assert forbidden.status_code == 403, forbidden.text

    # Admin global -> OK
    ok = client.delete(f"/api/v1/watch/nodes/{node['id']}", headers=_auth(admin_token))
    assert ok.status_code == 204, ok.text

    # Créateur -> OK sur un autre nœud
    node2 = _create_node(client, creator_token, title="R2")
    ok2 = client.delete(f"/api/v1/watch/nodes/{node2['id']}", headers=_auth(creator_token))
    assert ok2.status_code == 204, ok2.text


def test_node_not_found(client: TestClient) -> None:
    _, token = _make_user(client, "nf@example.com")
    resp = client.get("/api/v1/watch/nodes/999999", headers=_auth(token))
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------------- #
# Médias
# --------------------------------------------------------------------------- #
def test_upload_image_and_download(client: TestClient) -> None:
    _, token = _make_user(client, "m1@example.com")
    node = _create_node(client, token, title="R")
    payload = b"\x89PNG\r\n\x1a\n some-bytes"

    resp = _upload_media(client, token, node["id"], name="photo.png", content=payload)
    assert resp.status_code == 201, resp.text
    media = resp.json()
    assert media["kind"] == "image"
    assert media["filename"] == "photo.png"
    assert media["size"] == len(payload)
    assert media["url"] is None
    assert media["download_url"] == f"/api/v1/watch/media/{media['id']}/download"

    dl = client.get(media["download_url"], headers=_auth(token))
    assert dl.status_code == 200, dl.text
    assert dl.content == payload
    assert dl.headers["content-type"].startswith("image/png")


def test_add_youtube_link(client: TestClient) -> None:
    _, token = _make_user(client, "m2@example.com")
    node = _create_node(client, token, title="R")

    resp = client.post(
        f"/api/v1/watch/nodes/{node['id']}/media/link",
        json={"url": "https://youtube.com/watch?v=abc", "title": "Démo"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    media = resp.json()
    assert media["kind"] == "link"
    assert media["url"] == "https://youtube.com/watch?v=abc"
    assert media["title"] == "Démo"
    assert media["download_url"] is None


def test_list_media_and_node_detail(client: TestClient) -> None:
    _, token = _make_user(client, "m3@example.com")
    node = _create_node(client, token, title="R")
    _upload_media(client, token, node["id"])
    client.post(
        f"/api/v1/watch/nodes/{node['id']}/media/link",
        json={"url": "https://example.com"},
        headers=_auth(token),
    )

    listing = client.get(f"/api/v1/watch/nodes/{node['id']}/media", headers=_auth(token))
    assert listing.status_code == 200, listing.text
    assert len(listing.json()) == 2

    detail = client.get(f"/api/v1/watch/nodes/{node['id']}", headers=_auth(token)).json()
    assert len(detail["media"]) == 2


def test_upload_unsupported_type_415(client: TestClient) -> None:
    _, token = _make_user(client, "m4@example.com")
    node = _create_node(client, token, title="R")
    resp = _upload_media(
        client, token, node["id"], name="doc.pdf", content=b"%PDF", content_type="application/pdf"
    )
    assert resp.status_code == 415, resp.text


def test_upload_too_large_413(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _, token = _make_user(client, "m5@example.com")
    node = _create_node(client, token, title="R")

    monkeypatch.setattr(settings, "WATCH_MAX_UPLOAD_SIZE", 8)
    too_big = _upload_media(client, token, node["id"], content=b"0123456789")  # 10 > 8
    assert too_big.status_code == 413, too_big.text

    ok = _upload_media(client, token, node["id"], content=b"12345")
    assert ok.status_code == 201, ok.text


def test_delete_media_permissions(client: TestClient) -> None:
    _, creator_token = _make_user(client, "mc@example.com")
    _, other_token = _make_user(client, "mo@example.com")
    node = _create_node(client, creator_token, title="R")
    media = _upload_media(client, creator_token, node["id"]).json()

    forbidden = client.delete(f"/api/v1/watch/media/{media['id']}", headers=_auth(other_token))
    assert forbidden.status_code == 403, forbidden.text

    ok = client.delete(f"/api/v1/watch/media/{media['id']}", headers=_auth(creator_token))
    assert ok.status_code == 204, ok.text

    gone = client.get(f"/api/v1/watch/media/{media['id']}/download", headers=_auth(creator_token))
    assert gone.status_code == 404, gone.text


def test_download_link_media_404(client: TestClient) -> None:
    _, token = _make_user(client, "m6@example.com")
    node = _create_node(client, token, title="R")
    media = client.post(
        f"/api/v1/watch/nodes/{node['id']}/media/link",
        json={"url": "https://example.com"},
        headers=_auth(token),
    ).json()
    resp = client.get(f"/api/v1/watch/media/{media['id']}/download", headers=_auth(token))
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------------- #
# Commentaires
# --------------------------------------------------------------------------- #
def test_comment_crud_and_permissions(client: TestClient, admin_token: str) -> None:
    author_profile, author_token = _make_user(client, "ca@example.com", "Auteur")
    _, other_token = _make_user(client, "co@example.com")
    node = _create_node(client, author_token, title="R")

    # Création
    resp = client.post(
        f"/api/v1/watch/nodes/{node['id']}/comments",
        json={"body": "premier"},
        headers=_auth(author_token),
    )
    assert resp.status_code == 201, resp.text
    comment = resp.json()
    assert comment["body"] == "premier"
    assert comment["author"]["id"] == author_profile["id"]
    assert comment["node_id"] == node["id"]

    # Liste chronologique
    client.post(
        f"/api/v1/watch/nodes/{node['id']}/comments",
        json={"body": "second"},
        headers=_auth(other_token),
    )
    listing = client.get(f"/api/v1/watch/nodes/{node['id']}/comments", headers=_auth(author_token))
    assert [c["body"] for c in listing.json()] == ["premier", "second"]

    # Édition par un tiers -> 403 ; par l'auteur -> OK
    forbidden = client.patch(
        f"/api/v1/watch/comments/{comment['id']}",
        json={"body": "hack"},
        headers=_auth(other_token),
    )
    assert forbidden.status_code == 403, forbidden.text
    edited = client.patch(
        f"/api/v1/watch/comments/{comment['id']}",
        json={"body": "édité"},
        headers=_auth(author_token),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["body"] == "édité"

    # Suppression par un admin global -> OK
    ok = client.delete(f"/api/v1/watch/comments/{comment['id']}", headers=_auth(admin_token))
    assert ok.status_code == 204, ok.text


def test_comment_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/watch/nodes")
    assert resp.status_code == 401, resp.text
