"""Fixtures des tests du serveur MCP : environnement + client HTTP simulé.

Aucun appel réseau réel : ``respx`` intercepte les requêtes ``httpx`` et sert des
réponses fixées. Le client du module :mod:`jirou_mcp.server` est un singleton de
processus, remis à zéro entre les tests pour éviter les caches de résolution qui
fuient d'un test à l'autre.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
import respx

from jirou_mcp import server

BASE_URL = "https://jirou.test"
API = f"{BASE_URL}/api/v1"
TOKEN = "jir_pat_test-token"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure l'environnement attendu par ``JirouClient.from_env``."""
    monkeypatch.setenv("JIROU_API_URL", BASE_URL)
    monkeypatch.setenv("JIROU_TOKEN", TOKEN)


@pytest.fixture(autouse=True)
def _reset_client() -> Generator[None, None, None]:
    """Repart d'un client neuf (donc de caches vides) à chaque test."""
    server._client = None
    yield
    server._client = None


@pytest.fixture
def api() -> Generator[respx.MockRouter, None, None]:
    """Routeur ``respx`` monté sur l'URL de base de l'API."""
    with respx.mock(base_url=API, assert_all_called=False) as router:
        yield router


# --------------------------------------------------------------------------- #
# Charges utiles de référence (forme réelle de l'API Jirou)
# --------------------------------------------------------------------------- #
PROJECT = {
    "id": 7,
    "key": "JIR",
    "name": "Jirou",
    "description": "Le suivi de projet",
    "my_role": "admin",
    "members": [
        {
            "user_id": 3,
            "role": "member",
            "user": {
                "id": 3,
                "email": "dev@example.com",
                "full_name": "Dev",
                "role": "member",
            },
        }
    ],
}

ISSUE = {
    "id": 42,
    "key": "JIR-42",
    "project_id": 7,
    "type": "bug",
    "summary": "Le bouton ne répond pas",
    "status": "todo",
    "priority": "high",
    "story_points": 3,
    "assignee_id": 3,
    "reporter_id": 1,
    "epic_id": None,
    "sprint_id": None,
    "start_date": None,
    "due_date": None,
    "position": 0.0,
    "created_at": "2026-07-01T10:00:00Z",
    "updated_at": "2026-07-02T10:00:00Z",
    "labels": [{"id": 5, "name": "frontend", "color": "#111111"}],
    "assignee": {
        "id": 3,
        "email": "dev@example.com",
        "full_name": "Dev",
        "role": "member",
    },
    "reporter": {
        "id": 1,
        "email": "lead@example.com",
        "full_name": "Lead",
        "role": "admin",
    },
}

ISSUE_DETAIL = {
    **ISSUE,
    "description": "Cliquer ne déclenche rien en Safari.",
    "children": [],
    "progress": None,
    "dependencies": [],
}
