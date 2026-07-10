"""Tests d'intégration de l'import CSV de tickets (EPIC-05).

Couvre : import d'un CSV valide (champs/défauts), création & réutilisation de
labels, rattachement d'epic via ``epic_key`` (epic définie dans le CSV) et via
le champ de formulaire ``epic_id``, robustesse (lignes invalides ignorées mais
signalées), résolution de l'assigné (membre / non-membre) et les codes d'erreur
(viewer 403, en-tête/CSV invalide 400, epic_id du form invalide 422).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

VALID_PASSWORD = "s3cretpwd"

HEADER = "type,summary,description,priority,story_points,status,labels,assignee_email,epic_key"


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


def _import(
    client: TestClient,
    token: str,
    project_id: int,
    csv_text: str,
    epic_id: int | None = None,
):
    data: dict[str, str] = {}
    if epic_id is not None:
        data["epic_id"] = str(epic_id)
    return client.post(
        f"/api/v1/projects/{project_id}/issues/import",
        files={"file": ("import.csv", csv_text, "text/csv")},
        data=data,
        headers=_auth(token),
    )


# --------------------------------------------------------------------------- #
# Import valide
# --------------------------------------------------------------------------- #
def test_import_valid_csv_creates_issues_with_fields(client: TestClient) -> None:
    _, token = _make_user(client, "imp@example.com")
    proj = _create_project(client, token, key="IMP")
    csv_text = (
        HEADER + "\n"
        "story,Login page,Some desc,high,5,in_progress,,,\n"
        "bug,Crash on save,,lowest,,done,,,\n"
        "task,Refactor,,,,,,\n"
    )
    resp = _import(client, token, proj["id"], csv_text)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 3
    assert body["error_count"] == 0
    assert body["errors"] == []

    by_summary = {i["summary"]: i for i in body["issues"]}
    login = by_summary["Login page"]
    assert login["type"] == "story"
    assert login["priority"] == "high"
    assert login["story_points"] == 5
    assert login["status"] == "in_progress"
    assert login["key"].startswith("IMP-")

    crash = by_summary["Crash on save"]
    assert crash["type"] == "bug"
    assert crash["priority"] == "lowest"
    assert crash["status"] == "done"
    assert crash["story_points"] is None

    # Défauts appliqués (type/priority/status).
    refactor = by_summary["Refactor"]
    assert refactor["type"] == "task"
    assert refactor["priority"] == "medium"
    assert refactor["status"] == "todo"


def test_import_labels_created_and_reused(client: TestClient) -> None:
    _, token = _make_user(client, "lbl@example.com")
    proj = _create_project(client, token, key="LBL")
    csv_text = HEADER + "\ntask,First,,,,,backend;urgent,,\ntask,Second,,,,,Backend,,\n"
    resp = _import(client, token, proj["id"], csv_text)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 2

    # Les labels du projet : "backend" réutilisé (insensible à la casse) + "urgent".
    labels_resp = client.get(f"/api/v1/projects/{proj['id']}/labels", headers=_auth(token))
    names = sorted(label["name"].lower() for label in labels_resp.json())
    assert names == ["backend", "urgent"]

    by_summary = {i["summary"]: i for i in body["issues"]}
    first_ids = {label["id"] for label in by_summary["First"]["labels"]}
    second_ids = {label["id"] for label in by_summary["Second"]["labels"]}
    # "backend" partagé entre les deux tickets.
    assert first_ids & second_ids


# --------------------------------------------------------------------------- #
# Rattachement à une epic
# --------------------------------------------------------------------------- #
def test_import_epic_first_line_children_attached_by_summary(client: TestClient) -> None:
    _, token = _make_user(client, "epic@example.com")
    proj = _create_project(client, token, key="EPC")
    csv_text = (
        HEADER + "\n"
        "epic,Authentication,,,,,,,\n"
        "story,Login,,,,,,,Authentication\n"
        "task,Logout,,,,,,,authentication\n"
    )
    resp = _import(client, token, proj["id"], csv_text)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 3

    by_summary = {i["summary"]: i for i in body["issues"]}
    epic = by_summary["Authentication"]
    assert epic["type"] == "epic"
    assert epic["epic_id"] is None
    # Rattachement insensible à la casse au summary de l'epic créée.
    assert by_summary["Login"]["epic_id"] == epic["id"]
    assert by_summary["Logout"]["epic_id"] == epic["id"]


def test_import_attach_via_form_epic_id(client: TestClient) -> None:
    _, token = _make_user(client, "form@example.com")
    proj = _create_project(client, token, key="FRM")
    epic = client.post(
        f"/api/v1/projects/{proj['id']}/issues",
        json={"type": "epic", "summary": "Existing epic"},
        headers=_auth(token),
    ).json()

    csv_text = HEADER + "\n" + "task,Child A,,,,,,,\n" + "task,Child B,,,,,,,\n"
    resp = _import(client, token, proj["id"], csv_text, epic_id=epic["id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 2
    assert all(i["epic_id"] == epic["id"] for i in body["issues"])


def test_import_attach_via_existing_epic_key(client: TestClient) -> None:
    _, token = _make_user(client, "exist@example.com")
    proj = _create_project(client, token, key="EXK")
    epic = client.post(
        f"/api/v1/projects/{proj['id']}/issues",
        json={"type": "epic", "summary": "Platform"},
        headers=_auth(token),
    ).json()

    csv_text = HEADER + "\n" + f"task,Wired,,,,,,,{epic['key']}\n"
    resp = _import(client, token, proj["id"], csv_text)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["issues"][0]["epic_id"] == epic["id"]


def test_import_unknown_epic_key_warns_no_parent(client: TestClient) -> None:
    _, token = _make_user(client, "unk@example.com")
    proj = _create_project(client, token, key="UNK")
    csv_text = HEADER + "\n" + "task,Orphan,,,,,,,NOPE-999\n"
    resp = _import(client, token, proj["id"], csv_text)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1
    assert body["issues"][0]["epic_id"] is None
    assert any("epic_key" in e["message"] for e in body["errors"])


# --------------------------------------------------------------------------- #
# Robustesse : lignes invalides
# --------------------------------------------------------------------------- #
def test_import_invalid_rows_skipped_others_created(client: TestClient) -> None:
    _, token = _make_user(client, "rob@example.com")
    proj = _create_project(client, token, key="ROB")
    csv_text = (
        HEADER + "\n"
        "task,,,,,,,,\n"  # ligne 1 : summary vide -> ignorée
        "wizard,Bad type,,,,,,,\n"  # ligne 2 : type inconnu -> ignorée
        "task,Good one,,,,,,,\n"  # ligne 3 : valide
    )
    resp = _import(client, token, proj["id"], csv_text)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1
    assert body["issues"][0]["summary"] == "Good one"
    rows_with_errors = {e["row"] for e in body["errors"]}
    assert rows_with_errors == {1, 2}


def test_import_non_integer_story_points_warns_null(client: TestClient) -> None:
    _, token = _make_user(client, "pts@example.com")
    proj = _create_project(client, token, key="PTS")
    csv_text = HEADER + "\n" + "task,Estimate me,,,notanint,,,,\n"
    resp = _import(client, token, proj["id"], csv_text)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1
    assert body["issues"][0]["story_points"] is None
    assert any(e["row"] == 1 and "story_points" in e["message"] for e in body["errors"])


# --------------------------------------------------------------------------- #
# Assigné
# --------------------------------------------------------------------------- #
def test_import_assignee_member_and_non_member(client: TestClient) -> None:
    lead_profile, lead_token = _make_user(client, "lead@example.com", "Lead")
    member_profile, _ = _make_user(client, "member@example.com", "Member")
    _make_user(client, "outsider@example.com", "Outsider")
    proj = _create_project(client, lead_token, key="ASG")
    _add_member(client, lead_token, proj["id"], "member@example.com", "member")

    csv_text = (
        HEADER + "\n"
        "task,Assigned ok,,,,,,member@example.com,\n"
        "task,Assigned ko,,,,,,outsider@example.com,\n"
    )
    resp = _import(client, lead_token, proj["id"], csv_text)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 2

    by_summary = {i["summary"]: i for i in body["issues"]}
    assert by_summary["Assigned ok"]["assignee_id"] == member_profile["id"]
    # Non-membre : ticket créé sans assigné + avertissement.
    assert by_summary["Assigned ko"]["assignee_id"] is None
    assert any("outsider@example.com" in e["message"] for e in body["errors"])


# --------------------------------------------------------------------------- #
# Autorisations & erreurs d'entrée
# --------------------------------------------------------------------------- #
def test_import_viewer_forbidden(client: TestClient) -> None:
    _, lead_token = _make_user(client, "vlead@example.com")
    _make_user(client, "viewer@example.com")
    proj = _create_project(client, lead_token, key="VWI")
    _add_member(client, lead_token, proj["id"], "viewer@example.com", "viewer")
    viewer_token = _login(client, "viewer@example.com")

    csv_text = HEADER + "\n" + "task,Nope,,,,,,,\n"
    resp = _import(client, viewer_token, proj["id"], csv_text)
    assert resp.status_code == 403, resp.text


def test_import_empty_file_bad_request(client: TestClient) -> None:
    _, token = _make_user(client, "empty@example.com")
    proj = _create_project(client, token, key="EMP")
    resp = _import(client, token, proj["id"], "")
    assert resp.status_code == 400, resp.text


def test_import_missing_header_bad_request(client: TestClient) -> None:
    _, token = _make_user(client, "hdr@example.com")
    proj = _create_project(client, token, key="HDR")
    csv_text = "foo,bar\n1,2\n"
    resp = _import(client, token, proj["id"], csv_text)
    assert resp.status_code == 400, resp.text


def test_import_form_epic_id_not_an_epic_returns_422(client: TestClient) -> None:
    _, token = _make_user(client, "not@example.com")
    proj = _create_project(client, token, key="NOT")
    task = client.post(
        f"/api/v1/projects/{proj['id']}/issues",
        json={"type": "task", "summary": "Just a task"},
        headers=_auth(token),
    ).json()

    csv_text = HEADER + "\n" + "task,Child,,,,,,,\n"
    resp = _import(client, token, proj["id"], csv_text, epic_id=task["id"])
    assert resp.status_code == 422, resp.text
