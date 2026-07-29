"""Tests d'intégration de l'export/import de la veille R&D (domaine VEILLE).

Couvre l'archive ZIP produite par ``GET /watch/export`` (structure, manifeste,
fichiers embarqués), l'aller-retour export → import (fidélité de l'arbre, des
notes, des liens, des commentaires et des fichiers), les deux modes d'import
(additif par défaut, ``replace`` réservé aux admins) et la robustesse (archive
illisible, version inconnue, parent inconnu, cycle, fichier manquant, refs
dupliquées, entrée hors de ``media/``).

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


def _export_bytes(client: TestClient, token: str) -> bytes:
    resp = client.get("/api/v1/watch/export", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.content


def _import(
    client: TestClient,
    token: str,
    payload: bytes,
    *,
    replace: bool | None = None,
    name: str = "veille.zip",
) -> tuple[int, dict]:
    data = {} if replace is None else {"replace": str(replace).lower()}
    resp = client.post(
        "/api/v1/watch/import",
        files={"file": (name, payload, "application/zip")},
        data=data,
        headers=_auth(token),
    )
    return resp.status_code, resp.json() if resp.content else {}


def _zip_of(manifest: dict, files: dict[str, bytes] | None = None) -> bytes:
    """Construit une archive à la main (manifeste + entrées de médias)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, json.dumps(manifest))
        for name, content in (files or {}).items():
            zf.writestr(name, content)
    return buffer.getvalue()


def _nodes(client: TestClient, token: str) -> list[dict]:
    resp = client.get("/api/v1/watch/nodes", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


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


# --------------------------------------------------------------------------- #
# Import — aller-retour
# --------------------------------------------------------------------------- #
def test_round_trip_recreates_tree_media_and_comments(client: TestClient) -> None:
    token = _make_user(client, "round@example.com", "Bob Veille")
    root = _create_node(client, token, title="Téléopération", note="Note *riche*")
    child = _create_node(client, token, title="Gant haptique", parent_id=root["id"])
    client.post(
        f"/api/v1/watch/nodes/{child['id']}/media",
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
        headers=_auth(token),
    )
    client.post(
        f"/api/v1/watch/nodes/{child['id']}/media/link",
        json={"url": "https://example.org/paper"},
        headers=_auth(token),
    )
    client.post(
        f"/api/v1/watch/nodes/{child['id']}/comments",
        json={"body": "Prototype reçu"},
        headers=_auth(token),
    )
    archive = _export_bytes(client, token)

    # Import additif (mode par défaut) sur une veille déjà peuplée : duplique.
    status_code, result = _import(client, token, archive)
    assert status_code == 200, result
    assert result == {
        "nodes_created": 2,
        "media_created": 2,
        "comments_created": 1,
        "replaced": False,
        "error_count": 0,
        "errors": [],
    }

    summaries = _nodes(client, token)
    assert len(summaries) == 4
    imported = [s for s in summaries if s["id"] not in {root["id"], child["id"]}]
    imported_root = next(s for s in imported if s["parent_id"] is None)
    imported_child = next(s for s in imported if s["parent_id"] is not None)
    assert imported_child["parent_id"] == imported_root["id"]
    assert imported_child["media_count"] == 2
    assert imported_child["comment_count"] == 1

    detail = client.get(f"/api/v1/watch/nodes/{imported_root['id']}", headers=_auth(token)).json()
    assert detail["note"] == "Note *riche*"

    # Le fichier importé est bien re-téléchargeable, à l'identique.
    child_detail = client.get(
        f"/api/v1/watch/nodes/{imported_child['id']}", headers=_auth(token)
    ).json()
    image = next(m for m in child_detail["media"] if m["kind"] == "image")
    assert image["filename"] == "photo.png"
    download = client.get(f"/api/v1/watch/media/{image['id']}/download", headers=_auth(token))
    assert download.status_code == 200
    assert download.content == PNG_BYTES
    link = next(m for m in child_detail["media"] if m["kind"] == "link")
    assert link["url"] == "https://example.org/paper"

    comments = client.get(
        f"/api/v1/watch/nodes/{imported_child['id']}/comments", headers=_auth(token)
    ).json()
    assert [c["body"] for c in comments] == ["Prototype reçu"]
    assert comments[0]["author"]["email"] == "round@example.com"


def test_import_preserves_author_when_email_known(client: TestClient) -> None:
    """L'auteur d'un commentaire est retrouvé par e-mail ; sinon conservé à vide."""
    author_token = _make_user(client, "author@example.com", "Auteur")
    node = _create_node(client, author_token, title="Suivi")
    client.post(
        f"/api/v1/watch/nodes/{node['id']}/comments",
        json={"body": "Vu"},
        headers=_auth(author_token),
    )
    archive = _export_bytes(client, author_token)

    # Manifeste réécrit avec un auteur inconnu de l'instance.
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        manifest = json.loads(zf.read(MANIFEST_NAME))
    manifest["nodes"][0]["comments"][0]["author_email"] = "ghost@example.com"
    manifest["nodes"][0]["created_by_email"] = "ghost@example.com"

    importer_token = _make_user(client, "importer@example.com", "Importeur")
    status_code, result = _import(client, importer_token, _zip_of(manifest))
    assert status_code == 200, result
    assert result["comments_created"] == 1

    imported = next(s for s in _nodes(client, importer_token) if s["id"] != node["id"])
    comments = client.get(
        f"/api/v1/watch/nodes/{imported['id']}/comments", headers=_auth(importer_token)
    ).json()
    assert comments[0]["author"] is None
    # Le nœud, lui, revient à l'importateur (il peut donc le supprimer).
    assert (
        client.delete(
            f"/api/v1/watch/nodes/{imported['id']}", headers=_auth(importer_token)
        ).status_code
        == 204
    )


def test_import_accepts_plain_json_manifest(client: TestClient) -> None:
    """Un manifeste JSON nu (sans ZIP) est accepté : arbre sans fichiers."""
    token = _make_user(client, "json-import@example.com")
    manifest = {
        "version": ARCHIVE_VERSION,
        "nodes": [
            {"ref": "a", "parent_ref": None, "title": "Thème A", "type": "theme"},
            {"ref": "b", "parent_ref": "a", "title": "Techno B", "type": "techno"},
        ],
    }
    status_code, result = _import(client, token, json.dumps(manifest).encode(), name="veille.json")
    assert status_code == 200, result
    assert result["nodes_created"] == 2
    summaries = _nodes(client, token)
    assert {s["title"] for s in summaries} == {"Thème A", "Techno B"}


# --------------------------------------------------------------------------- #
# Import — mode remplacement
# --------------------------------------------------------------------------- #
def test_import_replace_requires_admin(client: TestClient) -> None:
    token = _make_user(client, "not-admin@example.com")
    status_code, body = _import(
        client, token, _zip_of({"version": ARCHIVE_VERSION, "nodes": []}), replace=True
    )
    assert status_code == 403
    assert "admin" in body["detail"].lower()


def test_import_replace_wipes_existing_watch(client: TestClient, admin_token: str) -> None:
    other_token = _make_user(client, "victim@example.com")
    old = _create_node(client, other_token, title="Ancien thème")
    client.post(
        f"/api/v1/watch/nodes/{old['id']}/media",
        files={"file": ("old.png", PNG_BYTES, "image/png")},
        headers=_auth(other_token),
    )
    old_files = list((Path(settings.UPLOAD_DIR) / "watch").rglob("*.png"))
    assert len(old_files) == 1

    manifest = {
        "version": ARCHIVE_VERSION,
        "nodes": [{"ref": "n1", "title": "Nouvelle veille", "type": "theme"}],
    }
    status_code, result = _import(client, admin_token, _zip_of(manifest), replace=True)
    assert status_code == 200, result
    assert result["replaced"] is True
    assert result["nodes_created"] == 1

    summaries = _nodes(client, admin_token)
    assert [s["title"] for s in summaries] == ["Nouvelle veille"]
    # Les fichiers de l'ancienne veille sont effacés après le commit.
    assert not old_files[0].exists()


def test_import_replace_false_is_additive(client: TestClient) -> None:
    token = _make_user(client, "additive@example.com")
    _create_node(client, token, title="Existant")
    manifest = {
        "version": ARCHIVE_VERSION,
        "nodes": [{"ref": "n1", "title": "Ajouté", "type": "theme"}],
    }
    status_code, result = _import(client, token, _zip_of(manifest), replace=False)
    assert status_code == 200, result
    assert result["replaced"] is False
    assert {s["title"] for s in _nodes(client, token)} == {"Existant", "Ajouté"}


# --------------------------------------------------------------------------- #
# Import — robustesse
# --------------------------------------------------------------------------- #
def test_import_rejects_unknown_version(client: TestClient) -> None:
    token = _make_user(client, "version@example.com")
    status_code, body = _import(client, token, _zip_of({"version": 99, "nodes": []}))
    assert status_code == 400
    assert "version" in body["detail"].lower()


def test_import_rejects_zip_without_manifest(client: TestClient) -> None:
    token = _make_user(client, "no-manifest@example.com")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("autre.txt", "rien")
    status_code, body = _import(client, token, buffer.getvalue())
    assert status_code == 400
    assert MANIFEST_NAME in body["detail"]


def test_import_rejects_garbage(client: TestClient) -> None:
    token = _make_user(client, "garbage@example.com")
    status_code, body = _import(client, token, b"ceci n'est pas une archive")
    assert status_code == 400
    assert "detail" in body


def test_import_rejects_too_many_nodes(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WATCH_MAX_IMPORT_NODES", 2)
    token = _make_user(client, "too-many@example.com")
    manifest = {
        "version": ARCHIVE_VERSION,
        "nodes": [{"ref": str(i), "title": f"N{i}"} for i in range(3)],
    }
    status_code, body = _import(client, token, _zip_of(manifest))
    assert status_code == 400
    assert "nœuds" in body["detail"]


def test_import_unknown_parent_becomes_root_with_warning(client: TestClient) -> None:
    token = _make_user(client, "orphan@example.com")
    manifest = {
        "version": ARCHIVE_VERSION,
        "nodes": [{"ref": "b", "parent_ref": "absent", "title": "Orphelin"}],
    }
    status_code, result = _import(client, token, _zip_of(manifest))
    assert status_code == 200, result
    assert result["nodes_created"] == 1
    assert result["error_count"] == 1
    assert "parent_ref" in result["errors"][0]["message"]
    assert _nodes(client, token)[0]["parent_id"] is None


def test_import_parent_cycle_becomes_root_with_warning(client: TestClient) -> None:
    token = _make_user(client, "cycle@example.com")
    manifest = {
        "version": ARCHIVE_VERSION,
        "nodes": [
            {"ref": "a", "parent_ref": "b", "title": "A"},
            {"ref": "b", "parent_ref": "a", "title": "B"},
        ],
    }
    status_code, result = _import(client, token, _zip_of(manifest))
    assert status_code == 200, result
    assert result["nodes_created"] == 2
    assert result["error_count"] >= 1
    assert any("cycle" in e["message"] for e in result["errors"])
    # Les deux nœuds existent, l'arbre reste exploitable (au moins une racine).
    summaries = _nodes(client, token)
    assert len(summaries) == 2
    assert any(s["parent_id"] is None for s in summaries)


def test_import_duplicate_refs_keeps_first(client: TestClient) -> None:
    token = _make_user(client, "dup@example.com")
    manifest = {
        "version": ARCHIVE_VERSION,
        "nodes": [
            {"ref": "a", "title": "Premier"},
            {"ref": "a", "title": "Doublon"},
        ],
    }
    status_code, result = _import(client, token, _zip_of(manifest))
    assert status_code == 200, result
    assert result["nodes_created"] == 1
    assert any("dupliquée" in e["message"] for e in result["errors"])
    assert [s["title"] for s in _nodes(client, token)] == ["Premier"]


def test_import_missing_media_entry_is_skipped(client: TestClient) -> None:
    token = _make_user(client, "no-file@example.com")
    manifest = {
        "version": ARCHIVE_VERSION,
        "nodes": [
            {
                "ref": "a",
                "title": "Avec média fantôme",
                "media": [
                    {
                        "kind": "image",
                        "filename": "absent.png",
                        "path": "media/a/absent.png",
                    },
                    {"kind": "link", "url": "https://ok.example"},
                    {"kind": "link", "url": None},
                ],
            }
        ],
    }
    status_code, result = _import(client, token, _zip_of(manifest))
    assert status_code == 200, result
    assert result["nodes_created"] == 1
    assert result["media_created"] == 1  # seul le lien valide passe
    messages = " ".join(e["message"] for e in result["errors"])
    assert "absent.png" in messages
    assert "lien sans URL" in messages


def test_import_rejects_media_entry_outside_media_dir(client: TestClient) -> None:
    """Une entrée hors de ``media/`` (tentative de traversal) est ignorée."""
    token = _make_user(client, "traversal@example.com")
    manifest = {
        "version": ARCHIVE_VERSION,
        "nodes": [
            {
                "ref": "a",
                "title": "Traversal",
                "media": [
                    {"kind": "image", "filename": "evil.png", "path": "../../evil.png"},
                    {
                        "kind": "image",
                        "filename": "evil2.png",
                        "path": "media/../../evil2.png",
                    },
                ],
            }
        ],
    }
    payload = _zip_of(manifest, {"../../evil.png": PNG_BYTES, "media/../../evil2.png": PNG_BYTES})
    status_code, result = _import(client, token, payload)
    assert status_code == 200, result
    assert result["media_created"] == 0
    assert result["error_count"] == 2
    # Rien n'a été écrit hors du dossier de veille.
    assert not list(Path(settings.UPLOAD_DIR).rglob("evil*.png"))


def test_import_media_too_large_is_skipped(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "WATCH_MAX_UPLOAD_SIZE", 10)
    token = _make_user(client, "big-media@example.com")
    manifest = {
        "version": ARCHIVE_VERSION,
        "nodes": [
            {
                "ref": "a",
                "title": "Gros média",
                "media": [{"kind": "image", "filename": "big.png", "path": "media/a/big.png"}],
            }
        ],
    }
    status_code, result = _import(client, token, _zip_of(manifest, {"media/a/big.png": b"x" * 100}))
    assert status_code == 200, result
    assert result["nodes_created"] == 1
    assert result["media_created"] == 0
    assert any("volumineux" in e["message"] for e in result["errors"])
    # Le fichier partiel est nettoyé.
    assert not list((Path(settings.UPLOAD_DIR) / "watch").rglob("*big.png"))


def test_import_rejects_oversized_archive(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Taille décompressée annoncée au-delà de la limite → 400 (anti « zip bomb »).

    L'archive reste petite *compressée* (elle passe donc la borne de lecture du
    téléversement) mais annonce 200 ko décompressés pour une limite de 2 ko.
    """
    monkeypatch.setattr(settings, "WATCH_MAX_IMPORT_SIZE", 2000)
    token = _make_user(client, "bomb@example.com")
    manifest = {"version": ARCHIVE_VERSION, "nodes": []}
    payload = _zip_of(manifest, {"media/a/pad.bin": b"0" * 200_000})
    assert len(payload) < 2000, "l'archive compressée doit rester sous la limite"
    status_code, body = _import(client, token, payload)
    assert status_code == 400
    assert "volumineuse" in body["detail"]


def test_import_rejects_oversized_upload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Téléversement dont les octets reçus dépassent la limite → 413."""
    monkeypatch.setattr(settings, "WATCH_MAX_IMPORT_SIZE", 100)
    token = _make_user(client, "big-upload@example.com")
    status_code, body = _import(client, token, b"x" * 5000)
    assert status_code == 413
    assert "volumineuse" in body["detail"]


def test_import_requires_auth(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/watch/import",
        files={"file": ("veille.zip", b"", "application/zip")},
    )
    assert resp.status_code == 401
