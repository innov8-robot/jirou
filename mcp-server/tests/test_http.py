"""Tests du transport HTTP : c'est la couche qui rend l'exposition publique sûre.

Le serveur HTTP n'a **pas** de jeton à lui — il n'existe donc aucune identité par
défaut à voler. Chaque requête doit porter un jeton Jirou, vérifié auprès de
l'API avant que le moindre outil ne s'exécute. Ces tests verrouillent ce
contrat, y compris ses cas limites (jeton absent, mal formé, refusé) et
l'isolation entre deux jetons différents.
"""

from __future__ import annotations

from collections.abc import Generator

import httpx
import pytest
import respx
from starlette.testclient import TestClient
from tests.conftest import API, BASE_URL

from jirou_mcp import context
from jirou_mcp.client import JirouError
from jirou_mcp.http import HEALTH_PATH, MCP_PATH, _ClientPool, build_app

TOKEN = "jir_pat_valide"
OTHER_TOKEN = "jir_pat_autre"


@pytest.fixture
def app_client(api: respx.MockRouter) -> Generator[TestClient, None, None]:
    """Client HTTP de test monté sur l'app MCP authentifiée.

    Le ``with`` est indispensable : il déclenche le *lifespan* ASGI, qui démarre
    le gestionnaire de sessions du transport streamable-http. Sans lui, tout
    appel échoue en « Task group is not initialized » — uvicorn s'en charge en
    production, un ``TestClient`` non contextualisé non.
    """
    # ``testserver`` est l'hôte que pose TestClient : sans lui dans la liste,
    # la protection anti-DNS-rebinding répondrait 421.
    with TestClient(build_app(BASE_URL, allowed_hosts=["testserver"])) as client:
        yield client


def _mock_me(api: respx.MockRouter, *, ok: bool = True) -> respx.Route:
    """Simule ``/auth/me``, la vérification du jeton par le middleware."""
    response = (
        httpx.Response(200, json={"id": 1, "email": "dev@example.com"})
        if ok
        else httpx.Response(401, json={"detail": "Identifiants invalides ou jeton expiré."})
    )
    return api.get("/auth/me").mock(return_value=response)


# --------------------------------------------------------------------------- #
# Sonde de vie
# --------------------------------------------------------------------------- #
def test_health_needs_no_token(app_client: TestClient) -> None:
    """Vérifier que le service tourne ne doit pas exiger de secret."""
    resp = app_client.get(HEALTH_PATH)
    assert resp.status_code == 200
    assert resp.json() == {"detail": "ok"}


# --------------------------------------------------------------------------- #
# Authentification
# --------------------------------------------------------------------------- #
def test_missing_authorization_is_401(app_client: TestClient) -> None:
    resp = app_client.post(MCP_PATH, json={})
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"
    assert "Jetons d'API" in resp.json()["detail"]


@pytest.mark.parametrize(
    "header",
    [
        "",
        "Bearer",
        "Bearer ",
        "Basic jir_pat_x",
        "Bearer pas-un-jeton",
        # Un access token JWT n'est pas un jeton d'API : refusé aussi.
        "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig",
    ],
)
def test_malformed_credentials_are_401(app_client: TestClient, header: str) -> None:
    resp = app_client.post(MCP_PATH, json={}, headers={"Authorization": header})
    assert resp.status_code == 401


def test_no_api_call_is_made_without_a_plausible_token(
    app_client: TestClient, api: respx.MockRouter
) -> None:
    """Un jeton mal formé est rejeté sans même solliciter l'API Jirou."""
    route = _mock_me(api)
    app_client.post(MCP_PATH, json={}, headers={"Authorization": "Bearer nope"})
    assert route.call_count == 0


def test_token_rejected_by_the_api_is_401(app_client: TestClient, api: respx.MockRouter) -> None:
    _mock_me(api, ok=False)
    resp = app_client.post(MCP_PATH, json={}, headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"
    # Le message explique quoi faire, sans détailler la cause exacte du refus.
    assert "Jetons d'API" in resp.json()["detail"]


def test_bearer_scheme_is_case_insensitive(app_client: TestClient, api: respx.MockRouter) -> None:
    _mock_me(api)
    resp = app_client.post(MCP_PATH, json={}, headers={"Authorization": f"bearer {TOKEN}"})
    # Passé l'authentification, le corps vide est rejeté par le transport MCP —
    # ce qui compte ici est que ce ne soit plus un 401.
    assert resp.status_code != 401


# --------------------------------------------------------------------------- #
# Bouclage MCP complet sur HTTP
# --------------------------------------------------------------------------- #
def test_initialize_succeeds_with_a_valid_token(
    app_client: TestClient, api: respx.MockRouter
) -> None:
    """Poignée de main MCP réelle à travers le middleware."""
    _mock_me(api)
    resp = app_client.post(
        MCP_PATH,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        },
    )
    assert resp.status_code == 200, resp.text
    assert "jirou" in resp.text


# --------------------------------------------------------------------------- #
# Le pool de clients : validation, réutilisation, isolation, bornage
# --------------------------------------------------------------------------- #
def test_pool_validates_once_then_reuses(api: respx.MockRouter) -> None:
    route = _mock_me(api)
    pool = _ClientPool(BASE_URL)
    first = pool.get(TOKEN)
    second = pool.get(TOKEN)
    assert first is second
    assert route.call_count == 1


def test_pool_rejects_an_invalid_token(api: respx.MockRouter) -> None:
    _mock_me(api, ok=False)
    with pytest.raises(JirouError):
        _ClientPool(BASE_URL).get(TOKEN)


def test_pool_isolates_tokens(api: respx.MockRouter) -> None:
    """Deux jetons distincts n'ont ni le même client ni les mêmes caches."""
    _mock_me(api)
    pool = _ClientPool(BASE_URL)
    assert pool.get(TOKEN) is not pool.get(OTHER_TOKEN)


def test_pool_is_bounded(api: respx.MockRouter) -> None:
    """Une rafale de jetons ne fait pas grossir la mémoire indéfiniment."""
    _mock_me(api)
    pool = _ClientPool(BASE_URL)
    for i in range(20):
        pool.get(f"jir_pat_{i}")
    assert len(pool._clients) <= 8


# --------------------------------------------------------------------------- #
# Contexte de requête
# --------------------------------------------------------------------------- #
def test_no_request_context_outside_http() -> None:
    """Hors requête HTTP (mode stdio), aucun client n'est imposé aux outils."""
    assert context.current_client() is None


def test_request_context_is_released(app_client: TestClient, api: respx.MockRouter) -> None:
    """Le client de requête ne fuit pas d'une requête à la suivante."""
    _mock_me(api)
    app_client.post(MCP_PATH, json={}, headers={"Authorization": f"Bearer {TOKEN}"})
    assert context.current_client() is None


def test_api_base_url_is_derived_from_config(api: respx.MockRouter) -> None:
    """Le pool cible bien l'API configurée (préfixe /api/v1 inclus)."""
    _mock_me(api)
    client = _ClientPool(BASE_URL).get(TOKEN)
    # httpx normalise la base_url avec un slash final.
    assert str(client._http.base_url).rstrip("/") == API
