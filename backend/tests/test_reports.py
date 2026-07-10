"""Tests de la génération de rapports (stats + synthèse LLM), réservée à l'admin.

Couvre l'autorisation (admin global uniquement), les rapports projet et global,
le comportement sans ``MISTRAL_API_KEY`` (aucune 503, note explicite) et le cas
d'une synthèse LLM monkeypatchée.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import rag as rag_service

VALID_PASSWORD = "s3cretpwd"


def _register(client: TestClient, email: str, full_name: str = "User") -> dict:
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": VALID_PASSWORD, "full_name": full_name},
    ).json()


def _login(client: TestClient, email: str) -> str:
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": VALID_PASSWORD},
    ).json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _member_token(client: TestClient, email: str) -> str:
    _register(client, email)
    return _login(client, email)


def _create_project(client: TestClient, token: str, key: str = "REP") -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"name": f"Project {key}", "key": key},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_issue(client: TestClient, token: str, project_id: int, **fields: object) -> dict:
    payload = {"type": "task", "summary": "Do something", **fields}
    resp = client.post(f"/api/v1/projects/{project_id}/issues", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# Autorisation
# --------------------------------------------------------------------------- #
def test_generate_forbidden_for_member(client: TestClient) -> None:
    token = _member_token(client, "member@example.com")
    resp = client.post("/api/v1/reports/generate", json={}, headers=_auth(token))
    assert resp.status_code == 403, resp.text


def test_generate_requires_auth(client: TestClient) -> None:
    resp = client.post("/api/v1/reports/generate", json={})
    assert resp.status_code == 401, resp.text


# --------------------------------------------------------------------------- #
# Rapport projet
# --------------------------------------------------------------------------- #
def test_generate_project_report_as_admin(client: TestClient, admin_token: str) -> None:
    owner = _member_token(client, "owner@example.com")
    proj = _create_project(client, owner, "REP")
    _create_issue(client, owner, proj["id"], type="bug", summary="A")
    _create_issue(client, owner, proj["id"], type="story", summary="B")

    resp = client.post(
        "/api/v1/reports/generate",
        json={"project_id": proj["id"]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["project_id"] == proj["id"]
    assert body["llm_used"] is False
    assert isinstance(body["generated_at"], str) and body["generated_at"]
    md = body["markdown"]
    assert md
    # En-tête du rapport projet + total cohérent + note d'indisponibilité IA.
    assert "# Rapport de projet" in md
    assert "Nombre total de tickets : **2**" in md
    assert "MISTRAL_API_KEY" in md


def test_generate_unknown_project_404(client: TestClient, admin_token: str) -> None:
    resp = client.post(
        "/api/v1/reports/generate",
        json={"project_id": 999999},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------------- #
# Rapport global
# --------------------------------------------------------------------------- #
def test_generate_global_report(client: TestClient, admin_token: str) -> None:
    owner = _member_token(client, "globalowner@example.com")
    proj = _create_project(client, owner, "GLB")
    _create_issue(client, owner, proj["id"], summary="Une tâche")

    resp = client.post("/api/v1/reports/generate", json={}, headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["project_id"] is None
    assert body["llm_used"] is False
    md = body["markdown"]
    assert md
    assert "# Rapport global" in md
    assert "Top projets par volume" in md


def test_generate_global_report_null_project_id(client: TestClient, admin_token: str) -> None:
    resp = client.post(
        "/api/v1/reports/generate", json={"project_id": None}, headers=_auth(admin_token)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["project_id"] is None


# --------------------------------------------------------------------------- #
# Synthèse LLM
# --------------------------------------------------------------------------- #
def test_generate_with_llm_synthesis(
    client: TestClient, admin_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "test-key")

    def _fake_chat(messages: list[dict]) -> str:
        return "Synthèse exécutive de test."

    monkeypatch.setattr(rag_service, "chat_completion", _fake_chat)

    owner = _member_token(client, "llmowner@example.com")
    proj = _create_project(client, owner, "LLM")
    _create_issue(client, owner, proj["id"], summary="Tâche")

    resp = client.post(
        "/api/v1/reports/generate",
        json={"project_id": proj["id"]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["llm_used"] is True
    md = body["markdown"]
    assert md.startswith("## Synthèse")
    assert "Synthèse exécutive de test." in md
    assert "MISTRAL_API_KEY" not in md


def test_generate_llm_failure_falls_back(
    client: TestClient, admin_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si l'appel LLM échoue, pas de 503 : rapport de stats + note, llm_used=false."""
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "test-key")

    def _boom(messages: list[dict]) -> str:
        raise rag_service.RagUnavailable("Mistral injoignable")

    monkeypatch.setattr(rag_service, "chat_completion", _boom)

    resp = client.post("/api/v1/reports/generate", json={}, headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["llm_used"] is False
    assert "MISTRAL_API_KEY" in body["markdown"]
