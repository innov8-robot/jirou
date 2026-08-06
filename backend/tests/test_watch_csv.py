"""Tests de l'import CSV de sous-nœuds sous un nœud de veille.

L'import est *ancré* : il greffe une branche sous un nœud choisi, sans jamais
toucher au reste de l'arbre. Comme le CSV est souvent produit par un LLM, la
robustesse compte autant que le chemin heureux : ces tests couvrent les
hiérarchies sur plusieurs niveaux, les liens externes, et surtout les données
douteuses (parent inconnu, cycle, doublon, type/statut inventés) qui doivent
dégrader proprement plutôt que faire échouer le lot.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

VALID_PASSWORD = "s3cretpwd"

HEADER = "title,parent,type,status,note,links"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(client: TestClient, email: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": VALID_PASSWORD, "full_name": "User"},
    )
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _create_node(client: TestClient, token: str, **body: object) -> dict:
    body.setdefault("title", "Ancre")
    resp = client.post("/api/v1/watch/nodes", json=body, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _import(client: TestClient, token: str, node_id: int, csv_text: str):
    return client.post(
        f"/api/v1/watch/nodes/{node_id}/import",
        files={"file": ("veille.csv", csv_text.encode("utf-8"), "text/csv")},
        headers=_auth(token),
    )


def _nodes(client: TestClient, token: str) -> list[dict]:
    resp = client.get("/api/v1/watch/nodes", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _by_title(client: TestClient, token: str) -> dict[str, dict]:
    return {n["title"]: n for n in _nodes(client, token)}


# --------------------------------------------------------------------------- #
# Import nominal
# --------------------------------------------------------------------------- #
def test_import_attaches_children_to_the_anchor(client: TestClient) -> None:
    token = _make_user(client, "csv-basic@example.com")
    anchor = _create_node(client, token, title="Mocap suit", type="theme")

    resp = _import(
        client,
        token,
        anchor["id"],
        f"{HEADER}\n"
        "Xsens MTw Awinda,,techno,promising,Précis mais cher,\n"
        "Rokoko Smartsuit,,techno,to_test,Moins cher,\n",
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["anchor_id"] == anchor["id"]
    assert result["nodes_created"] == 2
    assert result["error_count"] == 0

    nodes = _by_title(client, token)
    assert nodes["Xsens MTw Awinda"]["parent_id"] == anchor["id"]
    assert nodes["Xsens MTw Awinda"]["type"] == "techno"
    assert nodes["Xsens MTw Awinda"]["status"] == "promising"
    assert nodes["Rokoko Smartsuit"]["status"] == "to_test"


def test_import_builds_a_multi_level_subtree(client: TestClient) -> None:
    """``parent`` référence le titre d'une autre ligne : hiérarchie sans ids."""
    token = _make_user(client, "csv-tree@example.com")
    anchor = _create_node(client, token, title="Export")

    resp = _import(
        client,
        token,
        anchor["id"],
        f"{HEADER}\n"
        "Formats,,theme,,,\n"
        "CSV,Formats,solution,promising,,\n"
        "XLSX,Formats,solution,to_test,,\n"
        "Encodage Excel,XLSX,resource,,BOM UTF-8 requis,\n",
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["nodes_created"] == 4

    nodes = _by_title(client, token)
    assert nodes["Formats"]["parent_id"] == anchor["id"]
    assert nodes["CSV"]["parent_id"] == nodes["Formats"]["id"]
    assert nodes["Encodage Excel"]["parent_id"] == nodes["XLSX"]["id"]


def test_import_creates_external_links(client: TestClient) -> None:
    token = _make_user(client, "csv-links@example.com")
    anchor = _create_node(client, token)

    resp = _import(
        client,
        token,
        anchor["id"],
        f"{HEADER}\nXsens,,techno,,,https://xsens.com;https://youtu.be/demo\n",
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["links_created"] == 2

    node_id = _by_title(client, token)["Xsens"]["id"]
    detail = client.get(f"/api/v1/watch/nodes/{node_id}", headers=_auth(token)).json()
    assert {m["url"] for m in detail["media"]} == {
        "https://xsens.com",
        "https://youtu.be/demo",
    }
    assert all(m["kind"] == "link" for m in detail["media"])


def test_import_defaults_type_to_solution(client: TestClient) -> None:
    """Sous un nœud existant, on décrit des pistes — pas des thèmes."""
    token = _make_user(client, "csv-default@example.com")
    anchor = _create_node(client, token)
    _import(client, token, anchor["id"], f"{HEADER}\nSans type,,,,,\n")
    assert _by_title(client, token)["Sans type"]["type"] == "solution"


def test_import_accepts_minimal_header_and_bom(client: TestClient) -> None:
    """Un CSV réduit à ``title``, sauvegardé par Excel (BOM), reste lisible."""
    token = _make_user(client, "csv-minimal@example.com")
    anchor = _create_node(client, token)
    resp = client.post(
        f"/api/v1/watch/nodes/{anchor['id']}/import",
        files={"file": ("x.csv", "﻿title\nPiste A\nPiste B\n".encode(), "text/csv")},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["nodes_created"] == 2


def test_import_leaves_the_rest_of_the_tree_untouched(client: TestClient) -> None:
    """L'ancrage est le point clé : rien d'autre ne doit bouger."""
    token = _make_user(client, "csv-scope@example.com")
    other = _create_node(client, token, title="Autre thème")
    anchor = _create_node(client, token, title="Cible")

    _import(client, token, anchor["id"], f"{HEADER}\nGreffé,,,,,\n")

    nodes = _by_title(client, token)
    assert nodes["Autre thème"]["parent_id"] == other["parent_id"]
    assert nodes["Greffé"]["parent_id"] == anchor["id"]


def test_imported_nodes_are_spread_out(client: TestClient) -> None:
    """Les nœuds ne s'empilent pas au même point du graphe."""
    token = _make_user(client, "csv-pos@example.com")
    anchor = _create_node(client, token, pos_x=500, pos_y=500)
    _import(
        client,
        token,
        anchor["id"],
        f"{HEADER}\n" + "".join(f"N{i},,,,,\n" for i in range(4)),
    )
    created = [n for n in _nodes(client, token) if n["title"].startswith("N")]
    assert len({(n["pos_x"], n["pos_y"]) for n in created}) == 4


# --------------------------------------------------------------------------- #
# Robustesse : le CSV vient souvent d'un LLM
# --------------------------------------------------------------------------- #
def test_row_without_title_is_skipped_and_reported(client: TestClient) -> None:
    token = _make_user(client, "csv-notitle@example.com")
    anchor = _create_node(client, token)
    resp = _import(client, token, anchor["id"], f"{HEADER}\n,,techno,,,\nValide,,,,,\n")
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["nodes_created"] == 1
    assert any("title" in e["message"] for e in result["errors"])
    assert result["errors"][0]["row"] == 1


def test_unknown_type_and_status_degrade_with_a_warning(client: TestClient) -> None:
    token = _make_user(client, "csv-badenum@example.com")
    anchor = _create_node(client, token)
    resp = _import(client, token, anchor["id"], f"{HEADER}\nPiste,,licorne,peut-etre,,\n")
    assert resp.status_code == 200, resp.text
    result = resp.json()
    # La ligne est conservée : seules les valeurs fautives sont écartées.
    assert result["nodes_created"] == 1
    messages = " ".join(e["message"] for e in result["errors"])
    assert "licorne" in messages
    assert "peut-etre" in messages

    node = _by_title(client, token)["Piste"]
    assert node["type"] == "solution"
    assert node["status"] is None


def test_unknown_parent_falls_back_to_the_anchor(client: TestClient) -> None:
    token = _make_user(client, "csv-orphan@example.com")
    anchor = _create_node(client, token)
    resp = _import(client, token, anchor["id"], f"{HEADER}\nOrpheline,Fantôme,,,,\n")
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["nodes_created"] == 1
    assert any("Fantôme" in e["message"] for e in result["errors"])
    assert _by_title(client, token)["Orpheline"]["parent_id"] == anchor["id"]


def test_self_parent_falls_back_to_the_anchor(client: TestClient) -> None:
    token = _make_user(client, "csv-self@example.com")
    anchor = _create_node(client, token)
    resp = _import(client, token, anchor["id"], f"{HEADER}\nBoucle,Boucle,,,,\n")
    assert resp.status_code == 200, resp.text
    assert _by_title(client, token)["Boucle"]["parent_id"] == anchor["id"]
    assert any("elle-même" in e["message"] for e in resp.json()["errors"])


def test_parent_cycle_falls_back_to_the_anchor(client: TestClient) -> None:
    token = _make_user(client, "csv-cycle@example.com")
    anchor = _create_node(client, token)
    resp = _import(client, token, anchor["id"], f"{HEADER}\nA,B,,,,\nB,A,,,,\n")
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["nodes_created"] == 2
    assert any("cycle" in e["message"] for e in result["errors"])
    # Les deux nœuds existent et la branche reste exploitable.
    nodes = _by_title(client, token)
    assert {nodes["A"]["parent_id"], nodes["B"]["parent_id"]} <= {
        anchor["id"],
        nodes["A"]["id"],
        nodes["B"]["id"],
    }


def test_duplicate_title_is_reported(client: TestClient) -> None:
    token = _make_user(client, "csv-dup@example.com")
    anchor = _create_node(client, token)
    resp = _import(client, token, anchor["id"], f"{HEADER}\nMême,,,,,\nMême,,,,,\n")
    assert resp.status_code == 200, resp.text
    result = resp.json()
    # Les deux lignes sont créées ; seule la résolution de « parent » est ambiguë.
    assert result["nodes_created"] == 2
    assert any("doublon" in e["message"] for e in result["errors"])


def test_blank_lines_are_ignored_silently(client: TestClient) -> None:
    token = _make_user(client, "csv-blank@example.com")
    anchor = _create_node(client, token)
    resp = _import(client, token, anchor["id"], f"{HEADER}\nA,,,,,\n,,,,,\n\nB,,,,,\n")
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["nodes_created"] == 2
    assert result["error_count"] == 0


# --------------------------------------------------------------------------- #
# Rejets
# --------------------------------------------------------------------------- #
def test_missing_title_column_is_400(client: TestClient) -> None:
    token = _make_user(client, "csv-badheader@example.com")
    anchor = _create_node(client, token)
    resp = _import(client, token, anchor["id"], "nom,type\nX,techno\n")
    assert resp.status_code == 400
    assert "title" in resp.json()["detail"]


def test_empty_file_is_400(client: TestClient) -> None:
    token = _make_user(client, "csv-empty@example.com")
    anchor = _create_node(client, token)
    assert _import(client, token, anchor["id"], "").status_code == 400


def test_non_utf8_file_is_400(client: TestClient) -> None:
    token = _make_user(client, "csv-latin1@example.com")
    anchor = _create_node(client, token)
    resp = client.post(
        f"/api/v1/watch/nodes/{anchor['id']}/import",
        files={"file": ("x.csv", "title\nPrécis\n".encode("latin-1"), "text/csv")},
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert "UTF-8" in resp.json()["detail"]


def test_too_many_rows_is_400(client: TestClient, monkeypatch) -> None:  # noqa: ANN001
    from app.services import watch_csv

    monkeypatch.setattr(watch_csv, "MAX_ROWS", 3)
    token = _make_user(client, "csv-toolong@example.com")
    anchor = _create_node(client, token)
    resp = _import(
        client, token, anchor["id"], f"{HEADER}\n" + "".join(f"N{i},,,,,\n" for i in range(4))
    )
    assert resp.status_code == 400
    assert "lignes" in resp.json()["detail"]


def test_unknown_anchor_is_404(client: TestClient) -> None:
    token = _make_user(client, "csv-404@example.com")
    assert _import(client, token, 999999, f"{HEADER}\nX,,,,,\n").status_code == 404


def test_import_requires_auth(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/watch/nodes/1/import",
        files={"file": ("x.csv", b"title\nX\n", "text/csv")},
    )
    assert resp.status_code == 401


def test_general_archive_import_is_gone(client: TestClient) -> None:
    """L'import global d'archive a été retiré : seul l'import ancré subsiste."""
    token = _make_user(client, "csv-noglobal@example.com")
    resp = client.post(
        "/api/v1/watch/import",
        files={"file": ("veille.zip", b"PK\x03\x04", "application/zip")},
        headers=_auth(token),
    )
    assert resp.status_code == 404
