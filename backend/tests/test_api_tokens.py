"""Tests d'intégration des jetons d'API personnels (accès machine).

Couvre : création (secret renvoyé une seule fois, jamais restitué ensuite),
authentification d'un appel d'API avec un jeton, révocation et expiration,
isolation entre utilisateurs, rafraîchissement de ``last_used_at``, et le
cloisonnement clé de ce mécanisme — un jeton d'API ne peut ni gérer les jetons
ni changer le mot de passe.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.api_token import ApiToken
from app.services.api_token import TOKEN_PREFIX, hash_token

VALID_PASSWORD = "s3cretpwd"


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


def _create_token(
    client: TestClient, session: str, name: str = "Claude Code", **body: object
) -> dict:
    resp = client.post(
        "/api/v1/users/me/tokens",
        json={"name": name, **body},
        headers=_auth(session),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _list_tokens(client: TestClient, session: str) -> list[dict]:
    resp = client.get("/api/v1/users/me/tokens", headers=_auth(session))
    assert resp.status_code == 200, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# Création
# --------------------------------------------------------------------------- #
def test_create_token_returns_secret_once(client: TestClient) -> None:
    session = _make_user(client, "tok-create@example.com")
    created = _create_token(client, session, name="Portable")

    assert created["token"].startswith(TOKEN_PREFIX)
    assert len(created["token"]) > len(TOKEN_PREFIX) + 20
    assert created["name"] == "Portable"
    assert created["prefix"] == created["token"][:12]
    assert created["revoked_at"] is None
    assert created["expires_at"] is None
    assert created["last_used_at"] is None

    # La liste ne restitue jamais le secret.
    listed = _list_tokens(client, session)
    assert len(listed) == 1
    assert "token" not in listed[0]
    assert listed[0]["prefix"] == created["prefix"]


def test_created_tokens_are_unique(client: TestClient) -> None:
    session = _make_user(client, "tok-unique@example.com")
    first = _create_token(client, session, name="A")
    second = _create_token(client, session, name="B")
    assert first["token"] != second["token"]
    assert {t["name"] for t in _list_tokens(client, session)} == {"A", "B"}


def test_secret_is_never_stored_in_clear(client: TestClient, db_session: Session) -> None:
    session = _make_user(client, "tok-hash@example.com")
    created = _create_token(client, session)

    row = db_session.get(ApiToken, created["id"])
    assert row is not None
    assert row.token_hash == hash_token(created["token"])
    assert created["token"] not in row.token_hash


def test_create_token_with_expiry(client: TestClient) -> None:
    session = _make_user(client, "tok-expiry@example.com")
    created = _create_token(client, session, expires_in_days=30)
    assert created["expires_at"] is not None


def test_create_token_rejects_invalid_payload(client: TestClient) -> None:
    session = _make_user(client, "tok-bad@example.com")
    assert (
        client.post(
            "/api/v1/users/me/tokens", json={"name": ""}, headers=_auth(session)
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/users/me/tokens",
            json={"name": "X", "expires_in_days": 0},
            headers=_auth(session),
        ).status_code
        == 422
    )


# --------------------------------------------------------------------------- #
# Authentification avec un jeton
# --------------------------------------------------------------------------- #
def test_token_authenticates_api_calls(client: TestClient) -> None:
    session = _make_user(client, "tok-auth@example.com", "Alice Machine")
    raw = _create_token(client, session)["token"]

    me = client.get("/api/v1/auth/me", headers=_auth(raw))
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "tok-auth@example.com"


def test_token_grants_owner_permissions(client: TestClient) -> None:
    """Le jeton porte les droits de son propriétaire : il peut créer un ticket."""
    session = _make_user(client, "tok-perm@example.com")
    raw = _create_token(client, session)["token"]

    project = client.post(
        "/api/v1/projects",
        json={"name": "Machine", "key": "MCP"},
        headers=_auth(session),
    ).json()
    created = client.post(
        f"/api/v1/projects/{project['id']}/issues",
        json={"type": "task", "summary": "Créé via jeton"},
        headers=_auth(raw),
    )
    assert created.status_code == 201, created.text
    assert created.json()["summary"] == "Créé via jeton"


def test_unknown_token_is_rejected(client: TestClient) -> None:
    assert (
        client.get("/api/v1/auth/me", headers=_auth(f"{TOKEN_PREFIX}inexistant")).status_code == 401
    )


def test_revoked_token_is_rejected(client: TestClient) -> None:
    session = _make_user(client, "tok-revoke@example.com")
    created = _create_token(client, session)
    raw = created["token"]
    assert client.get("/api/v1/auth/me", headers=_auth(raw)).status_code == 200

    revoked = client.delete(f"/api/v1/users/me/tokens/{created['id']}", headers=_auth(session))
    assert revoked.status_code == 204
    assert client.get("/api/v1/auth/me", headers=_auth(raw)).status_code == 401

    # La ligne reste listée, marquée révoquée.
    listed = _list_tokens(client, session)
    assert listed[0]["revoked_at"] is not None


def test_revoke_is_idempotent(client: TestClient) -> None:
    session = _make_user(client, "tok-idem@example.com")
    created = _create_token(client, session)
    url = f"/api/v1/users/me/tokens/{created['id']}"
    assert client.delete(url, headers=_auth(session)).status_code == 204
    assert client.delete(url, headers=_auth(session)).status_code == 204


def test_expired_token_is_rejected(client: TestClient, db_session: Session) -> None:
    session = _make_user(client, "tok-expired@example.com")
    created = _create_token(client, session, expires_in_days=1)
    raw = created["token"]
    assert client.get("/api/v1/auth/me", headers=_auth(raw)).status_code == 200

    row = db_session.get(ApiToken, created["id"])
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    assert client.get("/api/v1/auth/me", headers=_auth(raw)).status_code == 401


def test_token_of_deactivated_user_is_rejected(client: TestClient, admin_token: str) -> None:
    email = "tok-disabled@example.com"
    session = _make_user(client, email)
    raw = _create_token(client, session)["token"]

    users = client.get("/api/v1/users", headers=_auth(admin_token)).json()
    user_id = next(u["id"] for u in users if u["email"] == email)
    patched = client.patch(
        f"/api/v1/users/{user_id}", json={"is_active": False}, headers=_auth(admin_token)
    )
    assert patched.status_code == 200, patched.text

    assert client.get("/api/v1/auth/me", headers=_auth(raw)).status_code == 401


def test_last_used_at_is_recorded(client: TestClient) -> None:
    session = _make_user(client, "tok-used@example.com")
    created = _create_token(client, session)
    assert created["last_used_at"] is None

    client.get("/api/v1/auth/me", headers=_auth(created["token"]))
    assert _list_tokens(client, session)[0]["last_used_at"] is not None


# --------------------------------------------------------------------------- #
# Cloisonnement : un jeton d'API n'est pas une session
# --------------------------------------------------------------------------- #
def test_api_token_cannot_manage_tokens(client: TestClient) -> None:
    """Un jeton fuité ne peut ni s'en créer d'autres ni révoquer ses pairs."""
    session = _make_user(client, "tok-noescalate@example.com")
    created = _create_token(client, session)
    raw = created["token"]

    assert client.get("/api/v1/users/me/tokens", headers=_auth(raw)).status_code == 401
    creation = client.post("/api/v1/users/me/tokens", json={"name": "Bis"}, headers=_auth(raw))
    assert creation.status_code == 401
    assert "session interactive" in creation.json()["detail"]
    assert (
        client.delete(f"/api/v1/users/me/tokens/{created['id']}", headers=_auth(raw)).status_code
        == 401
    )


def test_api_token_cannot_change_password(client: TestClient) -> None:
    session = _make_user(client, "tok-nopwd@example.com")
    raw = _create_token(client, session)["token"]

    resp = client.put(
        "/api/v1/users/me/password",
        json={"current_password": VALID_PASSWORD, "new_password": "an0therpwd"},
        headers=_auth(raw),
    )
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# Isolation entre utilisateurs
# --------------------------------------------------------------------------- #
def test_tokens_are_scoped_to_their_owner(client: TestClient) -> None:
    alice = _make_user(client, "tok-alice@example.com")
    bob = _make_user(client, "tok-bob@example.com")
    _create_token(client, alice, name="À Alice")

    assert _list_tokens(client, bob) == []


def test_cannot_revoke_someone_elses_token(client: TestClient) -> None:
    alice = _make_user(client, "tok-victim@example.com")
    bob = _make_user(client, "tok-thief@example.com")
    created = _create_token(client, alice)

    # 404 (et non 403) : ne pas révéler l'existence du jeton d'un tiers.
    assert (
        client.delete(f"/api/v1/users/me/tokens/{created['id']}", headers=_auth(bob)).status_code
        == 404
    )
    # Le jeton d'Alice fonctionne toujours.
    assert client.get("/api/v1/auth/me", headers=_auth(created["token"])).status_code == 200


def test_token_endpoints_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/users/me/tokens").status_code == 401
    assert client.post("/api/v1/users/me/tokens", json={"name": "X"}).status_code == 401
    assert client.delete("/api/v1/users/me/tokens/1").status_code == 401


def test_revoke_unknown_token_404(client: TestClient) -> None:
    session = _make_user(client, "tok-404@example.com")
    assert (
        client.delete("/api/v1/users/me/tokens/999999", headers=_auth(session)).status_code == 404
    )
