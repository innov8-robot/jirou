"""Tests d'intégration de la DOCUMENTATION (pages Markdown), projet et générale.

Couvre les documents de projet (création avec droits viewer/non-membre, liste,
détail, édition, suppression) ainsi que les documents généraux : création via
``POST /documents``, liste transverse ``GET /documents`` (généraux + projets du
membre, exclusion des autres projets) et permissions sur ``/documents/{id}``
(lecture par tout connecté, édition/suppression par l'auteur ou l'admin global).
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


def _create_document(
    client: TestClient, token: str, project_id: int, title: str = "Page", content: str = "# Hi"
) -> object:
    return client.post(
        f"/api/v1/projects/{project_id}/documents",
        json={"title": title, "content": content},
        headers=_auth(token),
    )


# --------------------------------------------------------------------------- #
# Création
# --------------------------------------------------------------------------- #
def test_create_document(client: TestClient) -> None:
    profile, token = _make_user(client, "author@example.com", "Author")
    proj = _create_project(client, token, key="DOC")

    resp = _create_document(client, token, proj["id"], title="Guide", content="# Intro")
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["project_id"] == proj["id"]
    assert doc["title"] == "Guide"
    assert doc["content"] == "# Intro"
    assert doc["author"]["id"] == profile["id"]
    assert "created_at" in doc and "updated_at" in doc


def test_create_document_default_empty_content(client: TestClient) -> None:
    _, token = _make_user(client, "empty@example.com")
    proj = _create_project(client, token, key="EMP")
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/documents",
        json={"title": "Sans contenu"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["content"] == ""


def test_viewer_cannot_create_document(client: TestClient) -> None:
    _, lead_token = _make_user(client, "lead@example.com")
    _make_user(client, "viewer@example.com")
    proj = _create_project(client, lead_token, key="VWR")
    _add_member(client, lead_token, proj["id"], "viewer@example.com", "viewer")

    viewer_token = _login(client, "viewer@example.com")
    resp = _create_document(client, viewer_token, proj["id"])
    assert resp.status_code == 403, resp.text


def test_non_member_cannot_create_document(client: TestClient) -> None:
    _, lead_token = _make_user(client, "owner@example.com")
    _make_user(client, "stranger@example.com")
    proj = _create_project(client, lead_token, key="NMB")

    stranger_token = _login(client, "stranger@example.com")
    resp = _create_document(client, stranger_token, proj["id"])
    assert resp.status_code in (403, 404), resp.text


# --------------------------------------------------------------------------- #
# Liste & détail
# --------------------------------------------------------------------------- #
def test_list_documents_summary_sorted_without_content(client: TestClient) -> None:
    _, token = _make_user(client, "lister@example.com")
    proj = _create_project(client, token, key="LST")

    first = _create_document(client, token, proj["id"], title="First").json()
    second = _create_document(client, token, proj["id"], title="Second").json()

    resp = client.get(f"/api/v1/projects/{proj['id']}/documents", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    items = resp.json()
    # Tri updated_at décroissant (tie-break id décroissant) : le plus récent d'abord.
    # NB : dans le harness de test tout se joue dans une seule transaction, où
    # ``now()`` est figé — les timestamps sont donc égaux et c'est l'id qui départage.
    assert [d["id"] for d in items] == [second["id"], first["id"]]
    # Résumé : pas de contenu, et champs exactement attendus.
    assert "content" not in items[0]
    assert set(items[0].keys()) == {"id", "project_id", "title", "author", "updated_at"}


def test_get_document_detail_with_content(client: TestClient) -> None:
    _, token = _make_user(client, "reader@example.com")
    proj = _create_project(client, token, key="DET")
    created = _create_document(client, token, proj["id"], content="## Body").json()

    resp = client.get(f"/api/v1/documents/{created['id']}", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    doc = resp.json()
    assert doc["content"] == "## Body"
    assert doc["id"] == created["id"]


def test_get_document_non_member_forbidden(client: TestClient) -> None:
    _, owner_token = _make_user(client, "docowner@example.com")
    _make_user(client, "intruder@example.com")
    proj = _create_project(client, owner_token, key="NMG")
    created = _create_document(client, owner_token, proj["id"]).json()

    intruder_token = _login(client, "intruder@example.com")
    resp = client.get(f"/api/v1/documents/{created['id']}", headers=_auth(intruder_token))
    assert resp.status_code in (403, 404), resp.text


# --------------------------------------------------------------------------- #
# Édition
# --------------------------------------------------------------------------- #
def test_patch_document_by_author_and_other_member(client: TestClient) -> None:
    _, lead_token = _make_user(client, "boss@example.com")
    _make_user(client, "mate@example.com")
    proj = _create_project(client, lead_token, key="EDT")
    _add_member(client, lead_token, proj["id"], "mate@example.com", "member")
    created = _create_document(client, lead_token, proj["id"], title="Orig").json()

    # L'auteur édite.
    ok = client.patch(
        f"/api/v1/documents/{created['id']}",
        json={"title": "Édité"},
        headers=_auth(lead_token),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["title"] == "Édité"

    # Un autre membre (member) édite aussi.
    mate_token = _login(client, "mate@example.com")
    ok2 = client.patch(
        f"/api/v1/documents/{created['id']}",
        json={"content": "par un collègue"},
        headers=_auth(mate_token),
    )
    assert ok2.status_code == 200, ok2.text
    assert ok2.json()["content"] == "par un collègue"


def test_patch_document_viewer_forbidden(client: TestClient) -> None:
    _, lead_token = _make_user(client, "chief@example.com")
    _make_user(client, "watcher@example.com")
    proj = _create_project(client, lead_token, key="VWP")
    _add_member(client, lead_token, proj["id"], "watcher@example.com", "viewer")
    created = _create_document(client, lead_token, proj["id"]).json()

    viewer_token = _login(client, "watcher@example.com")
    resp = client.patch(
        f"/api/v1/documents/{created['id']}",
        json={"title": "Nope"},
        headers=_auth(viewer_token),
    )
    assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------------- #
# Suppression
# --------------------------------------------------------------------------- #
def test_delete_document_by_author(client: TestClient) -> None:
    _, lead_token = _make_user(client, "del1@example.com")
    _make_user(client, "writer@example.com")
    proj = _create_project(client, lead_token, key="DLA")
    _add_member(client, lead_token, proj["id"], "writer@example.com", "member")

    writer_token = _login(client, "writer@example.com")
    created = _create_document(client, writer_token, proj["id"]).json()

    resp = client.delete(f"/api/v1/documents/{created['id']}", headers=_auth(writer_token))
    assert resp.status_code == 204, resp.text


def test_delete_document_member_non_author_forbidden(client: TestClient) -> None:
    _, lead_token = _make_user(client, "del2@example.com")
    _make_user(client, "aut@example.com")
    _make_user(client, "other@example.com")
    proj = _create_project(client, lead_token, key="DLM")
    _add_member(client, lead_token, proj["id"], "aut@example.com", "member")
    _add_member(client, lead_token, proj["id"], "other@example.com", "member")

    author_token = _login(client, "aut@example.com")
    created = _create_document(client, author_token, proj["id"]).json()

    other_token = _login(client, "other@example.com")
    resp = client.delete(f"/api/v1/documents/{created['id']}", headers=_auth(other_token))
    assert resp.status_code == 403, resp.text


def test_delete_document_by_lead(client: TestClient) -> None:
    _, lead_token = _make_user(client, "del3@example.com")
    _make_user(client, "auth2@example.com")
    proj = _create_project(client, lead_token, key="DLL")
    _add_member(client, lead_token, proj["id"], "auth2@example.com", "member")

    author_token = _login(client, "auth2@example.com")
    created = _create_document(client, author_token, proj["id"]).json()

    # Le lead du projet peut supprimer le document d'un autre.
    resp = client.delete(f"/api/v1/documents/{created['id']}", headers=_auth(lead_token))
    assert resp.status_code == 204, resp.text


def test_delete_document_not_found(client: TestClient) -> None:
    _, token = _make_user(client, "nf@example.com")
    resp = client.delete("/api/v1/documents/999999", headers=_auth(token))
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------------- #
# Documents généraux (non rattachés à un projet)
# --------------------------------------------------------------------------- #
def _create_general(
    client: TestClient, token: str, title: str = "Notes", content: str = "# Général"
) -> object:
    return client.post(
        "/api/v1/documents",
        json={"title": title, "content": content},
        headers=_auth(token),
    )


def test_create_general_document(client: TestClient) -> None:
    profile, token = _make_user(client, "gen@example.com", "Gen")
    resp = _create_general(client, token, title="Charte", content="# Règles")
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["project_id"] is None
    assert doc["title"] == "Charte"
    assert doc["content"] == "# Règles"
    assert doc["author"]["id"] == profile["id"]


def test_list_all_documents_scope(client: TestClient) -> None:
    # user1 : membre d'un projet + auteur d'un doc général.
    _, token1 = _make_user(client, "u1@example.com")
    proj1 = _create_project(client, token1, key="PJA")
    doc_proj1 = _create_document(client, token1, proj1["id"], title="Doc A").json()
    doc_general = _create_general(client, token1, title="Doc Global").json()

    # user2 : membre d'un autre projet dont user1 n'est pas membre.
    _, token2 = _make_user(client, "u2@example.com")
    proj2 = _create_project(client, token2, key="PJB")
    doc_proj2 = _create_document(client, token2, proj2["id"], title="Doc B").json()

    resp = client.get("/api/v1/documents", headers=_auth(token1))
    assert resp.status_code == 200, resp.text
    items = resp.json()
    ids = {d["id"] for d in items}
    # Voit son doc de projet et le doc général...
    assert doc_proj1["id"] in ids
    assert doc_general["id"] in ids
    # ...mais pas le doc d'un projet où il n'est pas membre.
    assert doc_proj2["id"] not in ids

    # Forme du résumé global : project null pour un doc général.
    by_id = {d["id"]: d for d in items}
    assert by_id[doc_general["id"]]["project"] is None
    assert by_id[doc_proj1["id"]]["project"]["key"] == "PJA"
    assert set(by_id[doc_general["id"]].keys()) == {
        "id",
        "title",
        "author",
        "updated_at",
        "project",
    }


def test_general_document_visible_to_other_user(client: TestClient) -> None:
    _, author_token = _make_user(client, "genauth@example.com")
    _, other_token = _make_user(client, "genother@example.com")
    created = _create_general(client, author_token, title="Public").json()

    # Un autre user connecté voit le doc général dans la liste globale...
    resp = client.get("/api/v1/documents", headers=_auth(other_token))
    assert resp.status_code == 200, resp.text
    assert created["id"] in {d["id"] for d in resp.json()}

    # ...et peut le lire en détail.
    detail = client.get(f"/api/v1/documents/{created['id']}", headers=_auth(other_token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["content"] == "# Général"


def test_general_document_edit_delete_permissions(client: TestClient) -> None:
    _, author_token = _make_user(client, "gedit@example.com")
    _, other_token = _make_user(client, "gother@example.com")
    created = _create_general(client, author_token, title="Orig").json()

    # L'auteur édite : OK.
    ok = client.patch(
        f"/api/v1/documents/{created['id']}",
        json={"title": "Édité"},
        headers=_auth(author_token),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["title"] == "Édité"

    # Un autre user non-admin ne peut ni éditer ni supprimer.
    ko = client.patch(
        f"/api/v1/documents/{created['id']}",
        json={"title": "Nope"},
        headers=_auth(other_token),
    )
    assert ko.status_code == 403, ko.text
    ko_del = client.delete(f"/api/v1/documents/{created['id']}", headers=_auth(other_token))
    assert ko_del.status_code == 403, ko_del.text

    # L'auteur supprime : OK.
    resp = client.delete(f"/api/v1/documents/{created['id']}", headers=_auth(author_token))
    assert resp.status_code == 204, resp.text


def test_general_document_admin_can_edit_and_delete(client: TestClient, admin_token: str) -> None:
    _, author_token = _make_user(client, "gadmin@example.com")
    created = _create_general(client, author_token, title="Orig").json()

    # Admin global édite le doc d'un autre : OK.
    ok = client.patch(
        f"/api/v1/documents/{created['id']}",
        json={"content": "par admin"},
        headers=_auth(admin_token),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["content"] == "par admin"

    # Admin global supprime : OK.
    resp = client.delete(f"/api/v1/documents/{created['id']}", headers=_auth(admin_token))
    assert resp.status_code == 204, resp.text
