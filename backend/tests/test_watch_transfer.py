"""Tests d'intégration de l'export d'archive de la veille (domaine VEILLE).

Couvre l'archive ZIP produite par ``GET /watch/export`` : structure, manifeste
auto-porté, fichiers embarqués, nom du fichier proposé, et le cas d'un média
disparu du disque.

L'archive est une **sauvegarde** : il n'y a pas d'import correspondant. L'ajout
de contenu passe par l'import CSV ancré (cf. ``test_watch_csv.py``).

Comme pour ``test_watch.py``, ``UPLOAD_DIR`` est redirigé vers un dossier
temporaire pour ne pas polluer le dépôt.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.schemas.watch_transfer import ARCHIVE_VERSION, MANIFEST_NAME

VALID_PASSWORD = "s3cretpwd"

# Octets d'un « fichier image » : seul le content-type est inspecté à l'upload.
PNG_BYTES = b"\x89PNG\r\n\x1a\n binary-content"


@pytest.fixture(autouse=True)
def _tmp_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirige le stockage des médias de veille vers un dossier temporaire."""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(client: TestClient, email: str, full_name: str = "User") -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": VALID_PASSWORD, "full_name": full_name},
    )
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _create_node(client: TestClient, token: str, **body: object) -> dict:
    body.setdefault("title", "Racine")
    resp = client.post("/api/v1/watch/nodes", json=body, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _export(client: TestClient, token: str) -> tuple[zipfile.ZipFile, dict]:
    """Télécharge l'archive et retourne ``(zip ouvert, manifeste décodé)``."""
    resp = client.get("/api/v1/watch/export", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    return zf, json.loads(zf.read(MANIFEST_NAME))


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def test_export_empty_watch(client: TestClient) -> None:
    token = _make_user(client, "export-empty@example.com")
    zf, manifest = _export(client, token)
    assert manifest["version"] == ARCHIVE_VERSION
    assert manifest["nodes"] == []
    assert zf.namelist() == [MANIFEST_NAME]


def test_export_filename_header(client: TestClient) -> None:
    token = _make_user(client, "export-name@example.com")
    resp = client.get("/api/v1/watch/export", headers=_auth(token))
    disposition = resp.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="veille-')
    assert disposition.endswith('.zip"')


def test_export_contains_tree_media_and_comments(client: TestClient) -> None:
    token = _make_user(client, "export-full@example.com", "Alice Veille")
    root = _create_node(client, token, title="Mocap suit", type="theme", note="# Notes")
    child = _create_node(
        client,
        token,
        title="Xsens",
        type="techno",
        parent_id=root["id"],
        status="promising",
        pos_x=120,
        pos_y=240,
    )
    client.post(
        f"/api/v1/watch/nodes/{child['id']}/media",
        files={"file": ("schema.png", PNG_BYTES, "image/png")},
        headers=_auth(token),
    )
    client.post(
        f"/api/v1/watch/nodes/{child['id']}/media/link",
        json={"url": "https://youtu.be/demo", "title": "Démo"},
        headers=_auth(token),
    )
    client.post(
        f"/api/v1/watch/nodes/{root['id']}/comments",
        json={"body": "À creuser"},
        headers=_auth(token),
    )

    zf, manifest = _export(client, token)
    by_title = {n["title"]: n for n in manifest["nodes"]}
    assert set(by_title) == {"Mocap suit", "Xsens"}

    exported_root = by_title["Mocap suit"]
    assert exported_root["parent_ref"] is None
    assert exported_root["note"] == "# Notes"
    assert exported_root["created_by_email"] == "export-full@example.com"
    assert [c["body"] for c in exported_root["comments"]] == ["À creuser"]

    exported_child = by_title["Xsens"]
    assert exported_child["parent_ref"] == exported_root["ref"]
    assert exported_child["type"] == "techno"
    assert exported_child["status"] == "promising"
    assert (exported_child["pos_x"], exported_child["pos_y"]) == (120, 240)

    kinds = {m["kind"]: m for m in exported_child["media"]}
    assert kinds["link"]["url"] == "https://youtu.be/demo"
    image_path = kinds["image"]["path"]
    assert image_path.startswith("media/")
    assert zf.read(image_path) == PNG_BYTES


def test_export_missing_file_keeps_metadata_without_path(client: TestClient) -> None:
    """Un fichier disparu du disque est exporté sans ``path`` (pas d'échec)."""
    token = _make_user(client, "export-missing@example.com")
    node = _create_node(client, token, title="Sans fichier")
    client.post(
        f"/api/v1/watch/nodes/{node['id']}/media",
        files={"file": ("gone.png", PNG_BYTES, "image/png")},
        headers=_auth(token),
    )
    for path in (Path(settings.UPLOAD_DIR) / "watch").rglob("*.png"):
        path.unlink()

    zf, manifest = _export(client, token)
    media = manifest["nodes"][0]["media"][0]
    assert media["filename"] == "gone.png"
    assert media["path"] is None
    assert zf.namelist() == [MANIFEST_NAME]


def test_export_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/watch/export").status_code == 401
