"""Tests du client HTTP : configuration, erreurs, résolution des identifiants.

La résolution est le cœur de l'ergonomie du serveur MCP — un agent désigne les
objets par clé/e-mail/nom, jamais par entier. Ces tests vérifient les traductions
et, surtout, que les messages d'échec listent les valeurs valides (c'est ce qui
permet à l'agent de se corriger seul plutôt que d'abandonner).
"""

from __future__ import annotations

import httpx
import pytest
import respx
from tests.conftest import PROJECT

from jirou_mcp.client import ConfigError, JirouClient, JirouError


def _client() -> JirouClient:
    return JirouClient.from_env()


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
def test_from_env_requires_url_and_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JIROU_API_URL", raising=False)
    monkeypatch.delenv("JIROU_TOKEN", raising=False)
    with pytest.raises(ConfigError) as excinfo:
        JirouClient.from_env()
    assert "JIROU_API_URL" in str(excinfo.value)
    assert "JIROU_TOKEN" in str(excinfo.value)


def test_from_env_reports_only_the_missing_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JIROU_TOKEN", raising=False)
    with pytest.raises(ConfigError) as excinfo:
        JirouClient.from_env()
    assert "JIROU_TOKEN" in str(excinfo.value)
    assert "JIROU_API_URL" not in str(excinfo.value)


def test_blank_env_counts_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JIROU_TOKEN", "   ")
    with pytest.raises(ConfigError):
        JirouClient.from_env()


def test_sends_bearer_token(api: respx.MockRouter) -> None:
    route = api.get("/projects").mock(return_value=httpx.Response(200, json=[]))
    _client().get("/projects")
    assert route.calls.last.request.headers["Authorization"].startswith("Bearer jir_pat_")


# --------------------------------------------------------------------------- #
# Erreurs
# --------------------------------------------------------------------------- #
def test_error_surfaces_api_detail(api: respx.MockRouter) -> None:
    api.get("/projects/9/issues").mock(
        return_value=httpx.Response(403, json={"detail": "Rôle projet insuffisant."})
    )
    with pytest.raises(JirouError) as excinfo:
        _client().get("/projects/9/issues")
    assert "Rôle projet insuffisant." in str(excinfo.value)
    assert "403" in str(excinfo.value)


def test_401_explains_how_to_fix(api: respx.MockRouter) -> None:
    api.get("/auth/me").mock(return_value=httpx.Response(401, json={"detail": "nope"}))
    with pytest.raises(JirouError) as excinfo:
        _client().get("/auth/me")
    assert "révoqué" in str(excinfo.value)
    assert "Jetons d'API" in str(excinfo.value)


def test_validation_error_is_flattened(api: respx.MockRouter) -> None:
    api.post("/projects/7/issues").mock(
        return_value=httpx.Response(
            422,
            json={
                "detail": [
                    {"loc": ["body", "summary"], "msg": "String should have at least 1 character"}
                ]
            },
        )
    )
    with pytest.raises(JirouError) as excinfo:
        _client().post("/projects/7/issues", {"summary": ""})
    assert "summary" in str(excinfo.value)


def test_network_failure_is_wrapped(api: respx.MockRouter) -> None:
    api.get("/projects").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(JirouError) as excinfo:
        _client().get("/projects")
    assert "impossible" in str(excinfo.value)


def test_204_returns_none(api: respx.MockRouter) -> None:
    api.delete("/comments/1").mock(return_value=httpx.Response(204))
    assert _client().delete("/comments/1") is None


def test_none_params_are_dropped(api: respx.MockRouter) -> None:
    route = api.get("/projects/7/issues").mock(return_value=httpx.Response(200, json=[]))
    _client().get("/projects/7/issues", status="todo", type=None, search=None)
    url = str(route.calls.last.request.url)
    assert "status=todo" in url
    assert "type=" not in url
    assert "search=" not in url


# --------------------------------------------------------------------------- #
# Résolution : projet
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("ref", ["JIR", "jir", "7", "Jirou", "jirou"])
def test_resolve_project_accepts_key_id_and_name(api: respx.MockRouter, ref: str) -> None:
    api.get("/projects").mock(return_value=httpx.Response(200, json=[PROJECT]))
    assert _client().project_id(ref) == 7


def test_resolve_project_unknown_lists_available(api: respx.MockRouter) -> None:
    api.get("/projects").mock(return_value=httpx.Response(200, json=[PROJECT]))
    with pytest.raises(JirouError) as excinfo:
        _client().project_id("ZZZ")
    message = str(excinfo.value)
    assert "ZZZ" in message
    assert "JIR (Jirou)" in message


def test_resolve_project_is_cached(api: respx.MockRouter) -> None:
    route = api.get("/projects").mock(return_value=httpx.Response(200, json=[PROJECT]))
    client = _client()
    client.project_id("JIR")
    client.project_id("JIR")
    assert route.call_count == 1


def test_resolve_project_refetches_before_failing(api: respx.MockRouter) -> None:
    """Un projet créé après le premier appel est trouvé au second essai."""
    route = api.get("/projects").mock(
        side_effect=[
            httpx.Response(200, json=[]),
            httpx.Response(200, json=[PROJECT]),
        ]
    )
    assert _client().project_id("JIR") == 7
    assert route.call_count == 2


# --------------------------------------------------------------------------- #
# Résolution : membres, epics, sprints, labels
# --------------------------------------------------------------------------- #
def test_resolve_user_id_from_email(api: respx.MockRouter) -> None:
    api.get("/projects/7").mock(return_value=httpx.Response(200, json=PROJECT))
    assert _client().resolve_user_id(7, "DEV@example.com") == 3


def test_resolve_user_id_non_member_lists_members(api: respx.MockRouter) -> None:
    api.get("/projects/7").mock(return_value=httpx.Response(200, json=PROJECT))
    with pytest.raises(JirouError) as excinfo:
        _client().resolve_user_id(7, "inconnu@example.com")
    assert "dev@example.com" in str(excinfo.value)


def test_resolve_epic_id_by_key_and_summary(api: respx.MockRouter) -> None:
    epics = [{"id": 11, "key": "JIR-3", "summary": "Authentification"}]
    api.get("/projects/7/issues").mock(return_value=httpx.Response(200, json=epics))
    client = _client()
    assert client.resolve_epic_id(7, "JIR-3") == 11
    assert client.resolve_epic_id(7, "authentification") == 11


def test_resolve_epic_id_unknown_lists_epics(api: respx.MockRouter) -> None:
    epics = [{"id": 11, "key": "JIR-3", "summary": "Authentification"}]
    api.get("/projects/7/issues").mock(return_value=httpx.Response(200, json=epics))
    with pytest.raises(JirouError) as excinfo:
        _client().resolve_epic_id(7, "Néant")
    assert "JIR-3 (Authentification)" in str(excinfo.value)


def test_resolve_sprint_id_by_name_id_and_active(api: respx.MockRouter) -> None:
    sprints = [
        {"id": 1, "name": "Sprint 1", "status": "completed"},
        {"id": 2, "name": "Sprint 2", "status": "active"},
    ]
    api.get("/projects/7/sprints").mock(return_value=httpx.Response(200, json=sprints))
    client = _client()
    assert client.resolve_sprint_id(7, "Sprint 1") == 1
    assert client.resolve_sprint_id(7, "2") == 2
    assert client.resolve_sprint_id(7, "active") == 2


def test_resolve_sprint_id_unknown_lists_sprints(api: respx.MockRouter) -> None:
    sprints = [{"id": 2, "name": "Sprint 2", "status": "active"}]
    api.get("/projects/7/sprints").mock(return_value=httpx.Response(200, json=sprints))
    with pytest.raises(JirouError) as excinfo:
        _client().resolve_sprint_id(7, "Sprint 9")
    assert "Sprint 2 [active]" in str(excinfo.value)


def test_resolve_label_ids_reuses_and_creates(api: respx.MockRouter) -> None:
    api.get("/projects/7/labels").mock(
        return_value=httpx.Response(200, json=[{"id": 5, "name": "frontend"}])
    )
    create = api.post("/projects/7/labels").mock(
        return_value=httpx.Response(201, json={"id": 9, "name": "perf"})
    )
    # Casse différente et doublon : le label existant est réutilisé une seule fois.
    assert _client().resolve_label_ids(7, ["Frontend", "perf", "frontend"]) == [5, 9]
    assert create.call_count == 1
    assert create.calls.last.request.read().decode().count("perf") == 1
