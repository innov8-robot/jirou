"""Tests d'intégration du domaine PROJETS (EPIC-04, JIR-23/24/25).

Réutilise les fixtures de ``conftest`` (client, db_session, admin_user,
admin_token). Couvre le CRUD projet, la gestion des membres, les autorisations
et le garde-fou « dernier admin / lead ».
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User

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
    """Enregistre un utilisateur (member global) et renvoie (profil, token)."""
    profile = _register(client, email, full_name)
    return profile, _login(client, email)


def _create_project(
    client: TestClient,
    token: str,
    name: str = "Demo Project",
    key: str = "DEMO",
    **extra: object,
) -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"name": name, "key": key, **extra},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _seed_user(db_session: Session, email: str, role: UserRole = UserRole.MEMBER) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(VALID_PASSWORD),
        full_name=email.split("@")[0],
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# --------------------------------------------------------------------------- #
# POST /projects
# --------------------------------------------------------------------------- #
def test_create_project_success(client: TestClient) -> None:
    profile, token = _make_user(client, "creator@example.com", "Creator")
    body = _create_project(client, token, key="ABC")

    assert body["key"] == "ABC"
    assert body["lead_id"] == profile["id"]
    assert body["my_role"] == "admin"
    assert body["member_count"] == 1
    assert body["is_archived"] is False

    # Le créateur est bien membre admin (visible dans le détail).
    detail = client.get(f"/api/v1/projects/{body['id']}", headers=_auth(token)).json()
    assert len(detail["members"]) == 1
    member = detail["members"][0]
    assert member["user_id"] == profile["id"]
    assert member["role"] == "admin"
    assert member["user"]["email"] == "creator@example.com"


def test_create_project_normalizes_key(client: TestClient) -> None:
    _, token = _make_user(client, "norm@example.com")
    body = _create_project(client, token, key="abc")
    assert body["key"] == "ABC"


def test_create_project_duplicate_key(client: TestClient) -> None:
    _, token = _make_user(client, "dup@example.com")
    _create_project(client, token, key="DUP")
    resp = client.post(
        "/api/v1/projects",
        json={"name": "Other", "key": "DUP"},
        headers=_auth(token),
    )
    assert resp.status_code == 409, resp.text


def test_create_project_invalid_key(client: TestClient) -> None:
    _, token = _make_user(client, "badkey@example.com")
    for bad in ("A", "1AB", "TOOLONG", "A-B"):
        resp = client.post(
            "/api/v1/projects",
            json={"name": "X", "key": bad},
            headers=_auth(token),
        )
        assert resp.status_code == 422, f"key={bad!r} -> {resp.status_code}"


def test_create_project_viewer_forbidden(client: TestClient, db_session: Session) -> None:
    _seed_user(db_session, "viewer@example.com", role=UserRole.VIEWER)
    token = _login(client, "viewer@example.com")
    resp = client.post(
        "/api/v1/projects",
        json={"name": "Nope", "key": "NOPE"},
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text


def test_create_project_requires_auth(client: TestClient) -> None:
    resp = client.post("/api/v1/projects", json={"name": "X", "key": "XX"})
    assert resp.status_code == 401, resp.text


# --------------------------------------------------------------------------- #
# GET /projects
# --------------------------------------------------------------------------- #
def test_list_projects_only_membership(client: TestClient) -> None:
    _, token_a = _make_user(client, "a@example.com")
    _, token_b = _make_user(client, "b@example.com")
    _create_project(client, token_a, name="A's", key="AAA")

    # B ne voit pas le projet de A.
    resp_b = client.get("/api/v1/projects", headers=_auth(token_b))
    assert resp_b.status_code == 200, resp_b.text
    assert resp_b.json() == []

    # A voit le sien, avec my_role=admin.
    resp_a = client.get("/api/v1/projects", headers=_auth(token_a)).json()
    assert len(resp_a) == 1
    assert resp_a[0]["key"] == "AAA"
    assert resp_a[0]["my_role"] == "admin"


def test_list_projects_include_archived(client: TestClient) -> None:
    _, token = _make_user(client, "arch@example.com")
    proj = _create_project(client, token, key="ARC")
    client.delete(f"/api/v1/projects/{proj['id']}", headers=_auth(token))

    # Par défaut, les projets archivés sont exclus.
    default = client.get("/api/v1/projects", headers=_auth(token)).json()
    assert default == []

    # include_archived=true les réintègre.
    included = client.get("/api/v1/projects?include_archived=true", headers=_auth(token)).json()
    assert len(included) == 1
    assert included[0]["is_archived"] is True


# --------------------------------------------------------------------------- #
# GET /projects/{id}
# --------------------------------------------------------------------------- #
def test_get_project_member_ok(client: TestClient) -> None:
    _, token = _make_user(client, "m@example.com")
    proj = _create_project(client, token, key="MEM")
    resp = client.get(f"/api/v1/projects/{proj['id']}", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == proj["id"]


def test_get_project_non_member_forbidden(client: TestClient) -> None:
    _, token_a = _make_user(client, "owner@example.com")
    _, token_b = _make_user(client, "stranger@example.com")
    proj = _create_project(client, token_a, key="PRV")
    resp = client.get(f"/api/v1/projects/{proj['id']}", headers=_auth(token_b))
    assert resp.status_code == 403, resp.text


def test_get_project_unknown_404(client: TestClient) -> None:
    _, token = _make_user(client, "seek@example.com")
    resp = client.get("/api/v1/projects/999999", headers=_auth(token))
    assert resp.status_code == 404, resp.text


def test_get_project_global_admin_non_member(client: TestClient, admin_token: str) -> None:
    _, token = _make_user(client, "someone@example.com")
    proj = _create_project(client, token, key="GAD")
    # L'admin global peut consulter sans être membre ; my_role est null.
    resp = client.get(f"/api/v1/projects/{proj['id']}", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["my_role"] is None


# --------------------------------------------------------------------------- #
# PATCH / DELETE /projects/{id}
# --------------------------------------------------------------------------- #
def test_patch_project_lead_ok(client: TestClient) -> None:
    _, token = _make_user(client, "lead@example.com")
    proj = _create_project(client, token, key="PAT")
    resp = client.patch(
        f"/api/v1/projects/{proj['id']}",
        json={"name": "Renamed", "color": "#ff0000"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["color"] == "#ff0000"


def test_patch_project_non_admin_member_forbidden(client: TestClient) -> None:
    _, lead_token = _make_user(client, "boss@example.com")
    guest, _ = _make_user(client, "guest@example.com")
    proj = _create_project(client, lead_token, key="RBAC")
    # Le lead ajoute guest en tant que member (non admin).
    client.post(
        f"/api/v1/projects/{proj['id']}/members",
        json={"email": "guest@example.com", "role": "member"},
        headers=_auth(lead_token),
    )
    guest_token = _login(client, "guest@example.com")
    resp = client.patch(
        f"/api/v1/projects/{proj['id']}",
        json={"name": "Hijack"},
        headers=_auth(guest_token),
    )
    assert resp.status_code == 403, resp.text


def test_delete_project_archives(client: TestClient) -> None:
    _, token = _make_user(client, "del@example.com")
    proj = _create_project(client, token, key="DEL")
    resp = client.delete(f"/api/v1/projects/{proj['id']}", headers=_auth(token))
    assert resp.status_code == 204, resp.text

    detail = client.get(f"/api/v1/projects/{proj['id']}", headers=_auth(token)).json()
    assert detail["is_archived"] is True


def test_global_admin_can_patch_any_project(client: TestClient, admin_token: str) -> None:
    _, token = _make_user(client, "otherlead@example.com")
    proj = _create_project(client, token, key="GAP")
    resp = client.patch(
        f"/api/v1/projects/{proj['id']}",
        json={"name": "By Admin"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "By Admin"


# --------------------------------------------------------------------------- #
# Membres — /projects/{id}/members
# --------------------------------------------------------------------------- #
def test_list_members(client: TestClient) -> None:
    _, token = _make_user(client, "lm@example.com")
    proj = _create_project(client, token, key="LM")
    resp = client.get(f"/api/v1/projects/{proj['id']}/members", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1


def test_add_member_by_email(client: TestClient) -> None:
    _, lead_token = _make_user(client, "l1@example.com")
    added, _ = _make_user(client, "newmember@example.com", "New Member")
    proj = _create_project(client, lead_token, key="ADD")
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/members",
        json={"email": "newmember@example.com", "role": "member"},
        headers=_auth(lead_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["user_id"] == added["id"]
    assert body["role"] == "member"
    assert body["user"]["full_name"] == "New Member"


def test_add_member_unknown_email_404(client: TestClient) -> None:
    _, lead_token = _make_user(client, "l2@example.com")
    proj = _create_project(client, lead_token, key="UNK")
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/members",
        json={"email": "ghost@example.com", "role": "member"},
        headers=_auth(lead_token),
    )
    assert resp.status_code == 404, resp.text


def test_add_member_duplicate_409(client: TestClient) -> None:
    _, lead_token = _make_user(client, "l3@example.com")
    _make_user(client, "twice@example.com")
    proj = _create_project(client, lead_token, key="TWI")
    payload = {"email": "twice@example.com", "role": "member"}
    first = client.post(
        f"/api/v1/projects/{proj['id']}/members", json=payload, headers=_auth(lead_token)
    )
    assert first.status_code == 201, first.text
    second = client.post(
        f"/api/v1/projects/{proj['id']}/members", json=payload, headers=_auth(lead_token)
    )
    assert second.status_code == 409, second.text


def test_add_member_forbidden_for_non_admin(client: TestClient) -> None:
    _, lead_token = _make_user(client, "l4@example.com")
    _make_user(client, "plainmember@example.com")
    _make_user(client, "target@example.com")
    proj = _create_project(client, lead_token, key="FRB")
    client.post(
        f"/api/v1/projects/{proj['id']}/members",
        json={"email": "plainmember@example.com", "role": "member"},
        headers=_auth(lead_token),
    )
    member_token = _login(client, "plainmember@example.com")
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/members",
        json={"email": "target@example.com", "role": "member"},
        headers=_auth(member_token),
    )
    assert resp.status_code == 403, resp.text


def test_change_member_role(client: TestClient) -> None:
    _, lead_token = _make_user(client, "l5@example.com")
    target, _ = _make_user(client, "promote-me@example.com")
    proj = _create_project(client, lead_token, key="CHG")
    client.post(
        f"/api/v1/projects/{proj['id']}/members",
        json={"email": "promote-me@example.com", "role": "member"},
        headers=_auth(lead_token),
    )
    resp = client.patch(
        f"/api/v1/projects/{proj['id']}/members/{target['id']}",
        json={"role": "admin"},
        headers=_auth(lead_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "admin"


def test_remove_member(client: TestClient) -> None:
    _, lead_token = _make_user(client, "l6@example.com")
    target, _ = _make_user(client, "remove-me@example.com")
    proj = _create_project(client, lead_token, key="RMV")
    client.post(
        f"/api/v1/projects/{proj['id']}/members",
        json={"email": "remove-me@example.com", "role": "member"},
        headers=_auth(lead_token),
    )
    resp = client.delete(
        f"/api/v1/projects/{proj['id']}/members/{target['id']}",
        headers=_auth(lead_token),
    )
    assert resp.status_code == 204, resp.text
    members = client.get(f"/api/v1/projects/{proj['id']}/members", headers=_auth(lead_token)).json()
    assert all(m["user_id"] != target["id"] for m in members)


def test_cannot_remove_last_admin_lead(client: TestClient) -> None:
    creator, lead_token = _make_user(client, "solo@example.com")
    proj = _create_project(client, lead_token, key="SOLO")
    # Le créateur est le seul admin ET le lead : retrait interdit (400).
    resp = client.delete(
        f"/api/v1/projects/{proj['id']}/members/{creator['id']}",
        headers=_auth(lead_token),
    )
    assert resp.status_code == 400, resp.text


def test_cannot_demote_last_admin_lead(client: TestClient) -> None:
    creator, lead_token = _make_user(client, "solo2@example.com")
    proj = _create_project(client, lead_token, key="SOL2")
    resp = client.patch(
        f"/api/v1/projects/{proj['id']}/members/{creator['id']}",
        json={"role": "member"},
        headers=_auth(lead_token),
    )
    assert resp.status_code == 400, resp.text


def test_change_member_role_forbidden_for_non_admin(client: TestClient) -> None:
    _, lead_token = _make_user(client, "l7@example.com")
    m1, _ = _make_user(client, "m1@example.com")
    m2, _ = _make_user(client, "m2@example.com")
    proj = _create_project(client, lead_token, key="NADM")
    for email in ("m1@example.com", "m2@example.com"):
        client.post(
            f"/api/v1/projects/{proj['id']}/members",
            json={"email": email, "role": "member"},
            headers=_auth(lead_token),
        )
    m1_token = _login(client, "m1@example.com")
    resp = client.patch(
        f"/api/v1/projects/{proj['id']}/members/{m2['id']}",
        json={"role": "admin"},
        headers=_auth(m1_token),
    )
    assert resp.status_code == 403, resp.text


def test_members_unknown_project_404(client: TestClient) -> None:
    _, token = _make_user(client, "np@example.com")
    resp = client.get("/api/v1/projects/999999/members", headers=_auth(token))
    assert resp.status_code == 404, resp.text
