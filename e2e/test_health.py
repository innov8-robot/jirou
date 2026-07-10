"""Santé de la stack : le backend et sa base de données répondent."""

from __future__ import annotations

import httpx


def test_backend_health(api_base_url: str) -> None:
    r = httpx.get(f"{api_base_url}/health", timeout=10.0)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_backend_db_health(api_base_url: str) -> None:
    r = httpx.get(f"{api_base_url}/health/db", timeout=10.0)
    assert r.status_code == 200
    body = r.json()
    assert body.get("database") == "ok"


def test_openapi_identity(api_base_url: str) -> None:
    r = httpx.get(f"{api_base_url}/openapi.json", timeout=10.0)
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "Jirou API"
