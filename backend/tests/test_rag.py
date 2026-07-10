"""Tests du chatbot RAG (EPIC-10) — sans réseau ni serveur Qdrant réel.

Stratégie :

- ``embed_texts`` est monkeypatché en un encodeur déterministe (hash de mots →
  vecteur de dimension ``RAG_EMBED_DIM``), pour que des textes partageant du
  vocabulaire soient proches en distance cosine.
- ``chat_completion`` renvoie une réponse factice qui récapitule le contexte
  reçu (permet d'assurer que le bon contenu a été mobilisé).
- Qdrant tourne **en mémoire** (``QdrantClient(location=":memory:")``), injecté
  via un override de ``get_qdrant_client`` partagé entre reindex et chat.

Couvre : indexation issues+comments+docs, récupération d'un ticket pertinent et
présence dans les sources, isolation stricte (un non-membre n'obtient pas le
contenu d'un projet), accès aux documents généraux, et les codes 503/statut
lorsque ``MISTRAL_API_KEY`` est absente ou présente.
"""

from __future__ import annotations

import hashlib
import math

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.core.config import settings
from app.services import rag as rag_service

VALID_PASSWORD = "s3cretpwd"


# --------------------------------------------------------------------------- #
# Faux embeddings / chat (déterministes, sans réseau)
# --------------------------------------------------------------------------- #
def _fake_embed(texts: list[str]) -> list[list[float]]:
    """Encode chaque texte en un vecteur normalisé basé sur le hash de ses mots."""
    dim = settings.RAG_EMBED_DIM
    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * dim
        for word in (text or "").lower().split():
            h = int(hashlib.sha256(word.encode()).hexdigest(), 16)
            vec[h % dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors


def _fake_chat(messages: list[dict]) -> str:
    """Renvoie une réponse factice incluant le contexte utilisateur reçu."""
    user_content = next((m["content"] for m in messages if m["role"] == "user"), "")
    return f"Réponse factice basée sur : {user_content}"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def rag_env(monkeypatch: pytest.MonkeyPatch) -> QdrantClient:
    """Configure clé Mistral, faux appels réseau et Qdrant en mémoire partagé."""
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(rag_service, "embed_texts", _fake_embed)
    monkeypatch.setattr(rag_service, "chat_completion", _fake_chat)
    client = QdrantClient(location=":memory:")
    monkeypatch.setattr(rag_service, "get_qdrant_client", lambda: client)
    return client


# --------------------------------------------------------------------------- #
# Helpers HTTP
# --------------------------------------------------------------------------- #
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


def _create_project(client: TestClient, token: str, key: str) -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"name": f"Project {key}", "key": key},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_issue(client: TestClient, token: str, project_id: int, summary: str, desc: str) -> dict:
    resp = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={"type": "task", "summary": summary, "description": desc},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# Statut & configuration
# --------------------------------------------------------------------------- #
def test_status_disabled_without_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "")
    _register(client, "u1@example.com")
    token = _login(client, "u1@example.com")
    resp = client.get("/api/v1/rag/status", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == {"enabled": False}


def test_status_enabled_with_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "test-key")
    _register(client, "u2@example.com")
    token = _login(client, "u2@example.com")
    resp = client.get("/api/v1/rag/status", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == {"enabled": True}


def test_chat_503_without_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "")
    _register(client, "u3@example.com")
    token = _login(client, "u3@example.com")
    resp = client.post("/api/v1/rag/chat", json={"question": "salut ?"}, headers=_auth(token))
    assert resp.status_code == 503
    assert "MISTRAL_API_KEY" in resp.json()["detail"]


def test_chat_422_without_question(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "test-key")
    _register(client, "u4@example.com")
    token = _login(client, "u4@example.com")
    resp = client.post("/api/v1/rag/chat", json={}, headers=_auth(token))
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Indexation + réponse via le service (Qdrant en mémoire)
# --------------------------------------------------------------------------- #
def test_reindex_and_answer_service(client: TestClient, db_session, rag_env: QdrantClient) -> None:
    """Reindex indexe issues+comments+docs ; answer retrouve le ticket pertinent."""
    from app.services.user import get_user_by_email

    _register(client, "owner@example.com")
    token = _login(client, "owner@example.com")
    project = _create_project(client, token, "ALPHA")
    issue = _create_issue(
        client,
        token,
        project["id"],
        "Migration base de données PostgreSQL",
        "Il faut migrer le cluster vers PostgreSQL 16 pour les performances.",
    )
    # Un commentaire sur ce ticket.
    resp = client.post(
        f"/api/v1/issues/{issue['key']}/comments",
        json={"body": "Attention au downtime pendant la migration."},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    # Un document de projet.
    resp = client.post(
        f"/api/v1/projects/{project['id']}/documents",
        json={"title": "Runbook migration", "content": "Étapes de migration PostgreSQL."},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text

    owner = get_user_by_email(db_session, "owner@example.com")

    # Chunks : 1 issue + 1 comment + 1 document.
    chunks = rag_service.build_chunks(db_session, [project["id"]])
    kinds = sorted(c["payload"]["kind"] for c in chunks)
    assert kinds == ["comment", "document", "issue"]

    indexed = rag_service.reindex(db_session, [project["id"]], client=rag_env)
    assert indexed == 3

    result = rag_service.answer(db_session, owner, "Comment migrer PostgreSQL ?", client=rag_env)
    assert "answer" in result and result["answer"]
    issue_keys = {s["issue_key"] for s in result["sources"]}
    assert issue["key"] in issue_keys


def test_non_member_gets_no_content(client: TestClient, db_session, rag_env: QdrantClient) -> None:
    """Un utilisateur non-membre n'obtient PAS le contenu d'un projet privé."""
    from app.services.user import get_user_by_email

    _register(client, "insider@example.com")
    insider_token = _login(client, "insider@example.com")
    project = _create_project(client, insider_token, "SECRT")
    _create_issue(
        client,
        insider_token,
        project["id"],
        "Clé API confidentielle",
        "Le token confidentiel est stocké dans le vault.",
    )

    # Indexe le projet privé.
    rag_service.reindex(db_session, [project["id"]], client=rag_env)

    # Un outsider, membre d'aucun projet.
    _register(client, "outsider@example.com")
    outsider = get_user_by_email(db_session, "outsider@example.com")

    result = rag_service.answer(
        db_session, outsider, "Quelle est la clé API confidentielle ?", client=rag_env
    )
    assert result["sources"] == []


def test_general_document_accessible_to_all(
    client: TestClient, db_session, rag_env: QdrantClient
) -> None:
    """Les documents généraux (project_id NULL) sont accessibles à tout utilisateur."""
    from app.services.user import get_user_by_email

    _register(client, "author@example.com")
    author_token = _login(client, "author@example.com")
    # Document général (non rattaché à un projet).
    resp = client.post(
        "/api/v1/documents",
        json={"title": "Guide onboarding", "content": "Bienvenue chez Jirou, voici le guide."},
        headers=_auth(author_token),
    )
    assert resp.status_code == 201, resp.text

    # Réindexe (les documents généraux sont inclus quel que soit project_ids).
    indexed = rag_service.reindex(db_session, [], client=rag_env)
    assert indexed == 1

    # Un utilisateur sans aucun projet accède quand même au document général.
    _register(client, "newcomer@example.com")
    newcomer = get_user_by_email(db_session, "newcomer@example.com")
    result = rag_service.answer(
        db_session, newcomer, "Où est le guide onboarding ?", client=rag_env
    )
    titles = {s["title"] for s in result["sources"]}
    assert "Guide onboarding" in titles


# --------------------------------------------------------------------------- #
# Endpoints /rag/reindex et /rag/chat (bout en bout)
# --------------------------------------------------------------------------- #
def test_reindex_and_chat_endpoints(client: TestClient, rag_env: QdrantClient) -> None:
    _register(client, "e2e@example.com")
    token = _login(client, "e2e@example.com")
    project = _create_project(client, token, "BETA")
    issue = _create_issue(
        client,
        token,
        project["id"],
        "Tableau de bord analytique",
        "Ajouter des graphiques de vélocité au tableau de bord.",
    )

    resp = client.post("/api/v1/rag/reindex", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["indexed"] >= 1

    resp = client.post(
        "/api/v1/rag/chat",
        json={"question": "Que faire pour le tableau de bord analytique ?"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "answer" in body and isinstance(body["sources"], list)
    assert any(s["issue_key"] == issue["key"] for s in body["sources"])
