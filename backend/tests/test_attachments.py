"""Tests d'intégration des PIÈCES JOINTES (EPIC-09, JIR-65).

Couvre l'upload multipart et ses métadonnées, le téléchargement (contenu +
content-type + Content-Disposition), la suppression (uploader ok / autre membre
403), l'interdiction faite au viewer d'uploader, et le dépassement de taille
(413) via une limite réduite par monkeypatch.

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
    """Redirige le stockage des pièces jointes vers un dossier temporaire."""
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


def _create_issue(client: TestClient, token: str, project_id: int) -> dict:
    resp = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={"type": "task", "summary": "Do something"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _upload(
    client: TestClient,
    token: str,
    key: str,
    *,
    name: str = "hello.txt",
    content: bytes = b"hello world",
    content_type: str = "text/plain",
) -> object:
    return client.post(
        f"/api/v1/issues/{key}/attachments",
        files={"file": (name, content, content_type)},
        headers=_auth(token),
    )


# --------------------------------------------------------------------------- #
# Upload & métadonnées
# --------------------------------------------------------------------------- #
def test_upload_and_metadata(client: TestClient) -> None:
    profile, token = _make_user(client, "up@example.com", "Uploader")
    proj = _create_project(client, token, key="ATT")
    issue = _create_issue(client, token, proj["id"])

    resp = _upload(client, token, issue["key"], name="report.pdf", content=b"%PDF-1.4 data")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["issue_id"] == issue["id"]
    assert body["filename"] == "report.pdf"
    assert body["content_type"] == "text/plain"
    assert body["size"] == len(b"%PDF-1.4 data")
    assert body["uploaded_by"]["id"] == profile["id"]
    assert body["download_url"] == f"/api/v1/attachments/{body['id']}/download"

    listing = client.get(f"/api/v1/issues/{issue['key']}/attachments", headers=_auth(token))
    assert listing.status_code == 200, listing.text
    assert [a["id"] for a in listing.json()] == [body["id"]]


def test_download_returns_content_and_headers(client: TestClient) -> None:
    _, token = _make_user(client, "dl@example.com")
    proj = _create_project(client, token, key="DWN")
    issue = _create_issue(client, token, proj["id"])
    payload = b"binary-content-\x00\x01\x02"
    up = _upload(
        client, token, issue["key"], name="data.bin", content=payload, content_type="image/png"
    ).json()

    resp = client.get(up["download_url"], headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.content == payload
    assert resp.headers["content-type"].startswith("image/png")
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert "data.bin" in resp.headers.get("content-disposition", "")


def test_viewer_cannot_upload(client: TestClient) -> None:
    _, lead_token = _make_user(client, "leadA@example.com")
    _make_user(client, "viewA@example.com")
    proj = _create_project(client, lead_token, key="VWA")
    _add_member(client, lead_token, proj["id"], "viewA@example.com", "viewer")
    issue = _create_issue(client, lead_token, proj["id"])

    viewer_token = _login(client, "viewA@example.com")
    resp = _upload(client, viewer_token, issue["key"])
    assert resp.status_code == 403, resp.text


def test_upload_too_large_returns_413(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _, token = _make_user(client, "big@example.com")
    proj = _create_project(client, token, key="BIG")
    issue = _create_issue(client, token, proj["id"])

    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 8)
    resp = _upload(client, token, issue["key"], content=b"0123456789")  # 10 > 8
    assert resp.status_code == 413, resp.text

    # Un fichier sous la limite passe.
    ok = _upload(client, token, issue["key"], content=b"12345")
    assert ok.status_code == 201, ok.text


# --------------------------------------------------------------------------- #
# Suppression
# --------------------------------------------------------------------------- #
def test_delete_uploader_ok_other_forbidden(client: TestClient) -> None:
    _, lead_token = _make_user(client, "ownerlead@example.com")
    _make_user(client, "uploader2@example.com")
    _make_user(client, "other2@example.com")
    proj = _create_project(client, lead_token, key="RM")
    _add_member(client, lead_token, proj["id"], "uploader2@example.com", "member")
    _add_member(client, lead_token, proj["id"], "other2@example.com", "member")
    issue = _create_issue(client, lead_token, proj["id"])

    uploader_token = _login(client, "uploader2@example.com")
    other_token = _login(client, "other2@example.com")
    att = _upload(client, uploader_token, issue["key"]).json()

    forbidden = client.delete(f"/api/v1/attachments/{att['id']}", headers=_auth(other_token))
    assert forbidden.status_code == 403, forbidden.text

    ok = client.delete(f"/api/v1/attachments/{att['id']}", headers=_auth(uploader_token))
    assert ok.status_code == 204, ok.text

    # Téléchargement d'une pièce jointe supprimée -> 404.
    gone = client.get(f"/api/v1/attachments/{att['id']}/download", headers=_auth(uploader_token))
    assert gone.status_code == 404, gone.text


def test_attachment_not_found(client: TestClient) -> None:
    _, token = _make_user(client, "nfa@example.com")
    resp = client.get("/api/v1/attachments/999999/download", headers=_auth(token))
    assert resp.status_code == 404, resp.text
