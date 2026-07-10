"""Fixtures e2e — testent la stack Jirou EN MARCHE (docker compose up).

Cible les ports HÔTE publiés par docker-compose. Surchargeable via variables
d'environnement :
  API_BASE_URL   (défaut http://localhost:8010)
  FRONTEND_URL   (défaut http://localhost:5199)
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8010")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5199")
API_V1 = f"{API_BASE_URL}/api/v1"


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return API_BASE_URL


@pytest.fixture(scope="session")
def frontend_url() -> str:
    return FRONTEND_URL


@pytest.fixture(scope="session")
def api() -> httpx.Client:
    """Client HTTP pointant sur le préfixe /api/v1."""
    with httpx.Client(base_url=API_V1, timeout=10.0) as client:
        yield client


def unique_email() -> str:
    """Email unique et valide (domaine non réservé) pour éviter les collisions."""
    return f"user_{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture
def new_user(api: httpx.Client) -> dict:
    """Crée un utilisateur frais et renvoie ses credentials + tokens."""
    email = unique_email()
    password = "password123"
    full_name = "E2E User"
    r = api.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert r.status_code in (200, 201), r.text
    login = api.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    tokens = login.json()
    return {
        "email": email,
        "password": password,
        "full_name": full_name,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "auth_header": {"Authorization": f"Bearer {tokens['access_token']}"},
    }
