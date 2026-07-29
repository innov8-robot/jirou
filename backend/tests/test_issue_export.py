"""Tests d'intégration de l'export CSV des tickets d'un projet (EPIC-05).

Couvre : en-tête et contenu du fichier (champs, labels multiples, epic parent,
sprint, dates, cellules vides), encodage UTF-8 avec BOM, nom de fichier proposé,
respect des filtres et du tri de la liste, absence de pagination (au-delà des
200 lignes du endpoint de liste), permissions (membre/viewer/non-membre) et
aller-retour export → import.
"""

from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

VALID_PASSWORD = "s3cretpwd"

EXPECTED_HEADER = [
    "key",
    "type",
    "summary",
    "description",
    "priority",
    "story_points",
    "status",
    "labels",
    "assignee_email",
    "epic_key",
    "sprint",
    "start_date",
    "due_date",
    "reporter_email",
    "created_at",
    "updated_at",
]


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


def _create_project(client: TestClient, token: str, key: str = "EXP") -> dict:
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


def _create_issue(client: TestClient, token: str, project_id: int, **body: object) -> dict:
    body.setdefault("type", "task")
    body.setdefault("summary", "Un ticket")
    resp = client.post(f"/api/v1/projects/{project_id}/issues", json=body, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _patch_issue(client: TestClient, token: str, key: str, **body: object) -> dict:
    resp = client.patch(f"/api/v1/issues/{key}", json=body, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _export(client: TestClient, token: str, project_id: int, **params: object):
    return client.get(
        f"/api/v1/projects/{project_id}/issues/export",
        params=params,
        headers=_auth(token),
    )


def _rows(response) -> list[dict[str, str]]:  # noqa: ANN001 - httpx.Response
    """Décode le CSV renvoyé (BOM inclus) en liste de dictionnaires."""
    text = response.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def _header(response) -> list[str]:  # noqa: ANN001 - httpx.Response
    text = response.content.decode("utf-8-sig")
    return next(csv.reader(io.StringIO(text)))


# --------------------------------------------------------------------------- #
# Contenu du fichier
# --------------------------------------------------------------------------- #
def test_export_header_and_content_type(client: TestClient) -> None:
    token = _make_user(client, "exp-header@example.com")
    proj = _create_project(client, token, key="EXH")
    resp = _export(client, token, proj["id"])
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert _header(resp) == EXPECTED_HEADER


def test_export_empty_project_has_header_only(client: TestClient) -> None:
    token = _make_user(client, "exp-empty@example.com")
    proj = _create_project(client, token, key="EXE")
    resp = _export(client, token, proj["id"])
    assert resp.status_code == 200
    assert _rows(resp) == []


def test_export_filename_uses_project_key(client: TestClient) -> None:
    token = _make_user(client, "exp-name@example.com")
    proj = _create_project(client, token, key="EXN")
    resp = _export(client, token, proj["id"])
    disposition = resp.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="EXN-tickets-')
    assert disposition.endswith('.csv"')


def test_export_is_utf8_with_bom(client: TestClient) -> None:
    """BOM présent : Excel affiche correctement les accents."""
    token = _make_user(client, "exp-bom@example.com")
    proj = _create_project(client, token, key="EXB")
    _create_issue(client, token, proj["id"], summary="Créé à l'été")
    resp = _export(client, token, proj["id"])
    assert resp.content.startswith(b"\xef\xbb\xbf")
    assert _rows(resp)[0]["summary"] == "Créé à l'été"


def test_export_fields_labels_epic_and_dates(client: TestClient) -> None:
    token = _make_user(client, "exp-full@example.com", "Alice")
    proj = _create_project(client, token, key="EXF")
    epic = _create_issue(client, token, proj["id"], type="epic", summary="Authentification")
    label_a = client.post(
        f"/api/v1/projects/{proj['id']}/labels",
        json={"name": "auth", "color": "#111111"},
        headers=_auth(token),
    ).json()
    label_b = client.post(
        f"/api/v1/projects/{proj['id']}/labels",
        json={"name": "frontend", "color": "#222222"},
        headers=_auth(token),
    ).json()
    story = _create_issue(
        client,
        token,
        proj["id"],
        type="story",
        summary="Écran de connexion",
        description="Formulaire email + mot de passe",
        priority="high",
        story_points=5,
        epic_id=epic["id"],
        label_ids=[label_a["id"], label_b["id"]],
        start_date="2026-08-01",
        due_date="2026-08-15",
    )
    # Le statut n'est pas dans le payload de création : il se pose par PATCH.
    _patch_issue(client, token, story["key"], status="in_progress")

    rows = {r["key"]: r for r in _rows(_export(client, token, proj["id"]))}
    assert set(rows) == {epic["key"], story["key"]}

    exported = rows[story["key"]]
    assert exported["type"] == "story"
    assert exported["summary"] == "Écran de connexion"
    assert exported["description"] == "Formulaire email + mot de passe"
    assert exported["priority"] == "high"
    assert exported["story_points"] == "5"
    assert exported["status"] == "in_progress"
    assert set(exported["labels"].split(";")) == {"auth", "frontend"}
    assert exported["epic_key"] == epic["key"]
    assert exported["start_date"] == "2026-08-01"
    assert exported["due_date"] == "2026-08-15"
    assert exported["reporter_email"] == "exp-full@example.com"
    assert exported["created_at"] and exported["updated_at"]

    # L'epic elle-même n'a pas de parent : cellule vide, pas "None".
    assert rows[epic["key"]]["epic_key"] == ""


def test_export_empty_cells_for_absent_values(client: TestClient) -> None:
    token = _make_user(client, "exp-blank@example.com")
    proj = _create_project(client, token, key="EXV")
    issue = _create_issue(client, token, proj["id"], summary="Minimal")
    row = _rows(_export(client, token, proj["id"]))[0]
    assert row["key"] == issue["key"]
    for column in (
        "description",
        "story_points",
        "labels",
        "assignee_email",
        "epic_key",
        "sprint",
        "start_date",
        "due_date",
    ):
        assert row[column] == "", column


def test_export_includes_assignee_and_sprint(client: TestClient) -> None:
    token = _make_user(client, "exp-lead@example.com")
    member_email = "exp-dev@example.com"
    _make_user(client, member_email, "Dev")
    proj = _create_project(client, token, key="EXS")
    _add_member(client, token, proj["id"], member_email, "member")
    members = client.get(f"/api/v1/projects/{proj['id']}", headers=_auth(token)).json()["members"]
    dev_id = next(m["user_id"] for m in members if m["user"]["email"] == member_email)

    sprint = client.post(
        f"/api/v1/projects/{proj['id']}/sprints",
        json={"name": "Sprint 1"},
        headers=_auth(token),
    ).json()
    issue = _create_issue(client, token, proj["id"], summary="Assignée", assignee_id=dev_id)
    moved = client.patch(
        f"/api/v1/issues/{issue['key']}/backlog-move",
        json={"sprint_id": sprint["id"], "position": 0},
        headers=_auth(token),
    )
    assert moved.status_code == 200, moved.text

    row = _rows(_export(client, token, proj["id"]))[0]
    assert row["assignee_email"] == member_email
    assert row["sprint"] == "Sprint 1"


# --------------------------------------------------------------------------- #
# Filtres, tri, volumétrie
# --------------------------------------------------------------------------- #
def test_export_respects_filters(client: TestClient) -> None:
    token = _make_user(client, "exp-filter@example.com")
    proj = _create_project(client, token, key="EXP")
    _create_issue(client, token, proj["id"], type="bug", summary="Un bug")
    _create_issue(client, token, proj["id"], type="task", summary="Une tâche")

    rows = _rows(_export(client, token, proj["id"], type="bug"))
    assert [r["summary"] for r in rows] == ["Un bug"]

    rows = _rows(_export(client, token, proj["id"], search="tâche"))
    assert [r["summary"] for r in rows] == ["Une tâche"]

    rows = _rows(_export(client, token, proj["id"], status="done"))
    assert rows == []


def test_export_respects_sort(client: TestClient) -> None:
    token = _make_user(client, "exp-sort@example.com")
    proj = _create_project(client, token, key="EXO")
    _create_issue(client, token, proj["id"], summary="Aaa")
    _create_issue(client, token, proj["id"], summary="Bbb")

    ascending = [r["summary"] for r in _rows(_export(client, token, proj["id"], sort="summary"))]
    descending = [r["summary"] for r in _rows(_export(client, token, proj["id"], sort="-summary"))]
    assert ascending == ["Aaa", "Bbb"]
    assert descending == ["Bbb", "Aaa"]


def test_export_unknown_sort_returns_422(client: TestClient) -> None:
    token = _make_user(client, "exp-badsort@example.com")
    proj = _create_project(client, token, key="EXZ")
    resp = _export(client, token, proj["id"], sort="couleur")
    assert resp.status_code == 422


def test_export_is_not_paginated(client: TestClient) -> None:
    """Au-delà de la limite de la liste (200), toutes les lignes sont exportées."""
    token = _make_user(client, "exp-many@example.com")
    proj = _create_project(client, token, key="EXM")
    csv_text = "type,summary\n" + "".join(f"task,Ticket {i}\n" for i in range(210))
    imported = client.post(
        f"/api/v1/projects/{proj['id']}/issues/import",
        files={"file": ("bulk.csv", csv_text, "text/csv")},
        headers=_auth(token),
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["created"] == 210

    assert len(_rows(_export(client, token, proj["id"]))) == 210


# --------------------------------------------------------------------------- #
# Permissions
# --------------------------------------------------------------------------- #
def test_export_allowed_for_viewer(client: TestClient) -> None:
    """L'export est en lecture seule : un viewer y a droit (contrairement à l'import)."""
    token = _make_user(client, "exp-owner@example.com")
    viewer_email = "exp-viewer@example.com"
    viewer_token = _make_user(client, viewer_email)
    proj = _create_project(client, token, key="EXW")
    _add_member(client, token, proj["id"], viewer_email, "viewer")
    _create_issue(client, token, proj["id"], summary="Visible")

    resp = _export(client, viewer_token, proj["id"])
    assert resp.status_code == 200
    assert [r["summary"] for r in _rows(resp)] == ["Visible"]


def test_export_forbidden_for_non_member(client: TestClient) -> None:
    token = _make_user(client, "exp-in@example.com")
    outsider_token = _make_user(client, "exp-out@example.com")
    proj = _create_project(client, token, key="EXX")
    assert _export(client, outsider_token, proj["id"]).status_code == 403


def test_export_requires_auth(client: TestClient) -> None:
    token = _make_user(client, "exp-anon@example.com")
    proj = _create_project(client, token, key="EXA")
    resp = client.get(f"/api/v1/projects/{proj['id']}/issues/export")
    assert resp.status_code == 401


def test_export_unknown_project_404(client: TestClient) -> None:
    token = _make_user(client, "exp-404@example.com")
    assert _export(client, token, 999999).status_code == 404


# --------------------------------------------------------------------------- #
# Aller-retour export → import
# --------------------------------------------------------------------------- #
def test_exported_csv_can_be_reimported(client: TestClient) -> None:
    """Le fichier exporté est réimportable : mêmes champs, epic parent retrouvée."""
    token = _make_user(client, "exp-round@example.com")
    proj = _create_project(client, token, key="EXR")
    epic = _create_issue(client, token, proj["id"], type="epic", summary="Socle")
    label = client.post(
        f"/api/v1/projects/{proj['id']}/labels",
        json={"name": "infra", "color": "#333333"},
        headers=_auth(token),
    ).json()
    story = _create_issue(
        client,
        token,
        proj["id"],
        type="story",
        summary="Mise en place CI",
        priority="high",
        story_points=3,
        epic_id=epic["id"],
        label_ids=[label["id"]],
    )
    _patch_issue(client, token, story["key"], status="in_progress")
    exported = _export(client, token, proj["id"])

    reimported = client.post(
        f"/api/v1/projects/{proj['id']}/issues/import",
        files={"file": ("round.csv", exported.content, "text/csv")},
        headers=_auth(token),
    )
    assert reimported.status_code == 200, reimported.text
    result = reimported.json()
    assert result["created"] == 2
    assert result["error_count"] == 0, result["errors"]

    copies = {i["summary"]: i for i in result["issues"]}
    assert set(copies) == {"Socle", "Mise en place CI"}
    story_copy = copies["Mise en place CI"]
    assert story_copy["type"] == "story"
    assert story_copy["priority"] == "high"
    assert story_copy["story_points"] == 3
    assert story_copy["status"] == "in_progress"
    assert [label["name"] for label in story_copy["labels"]] == ["infra"]
    # ``epic_key`` désignait une epic existante du projet : le parent est retrouvé.
    assert story_copy["epic_id"] == epic["id"]
