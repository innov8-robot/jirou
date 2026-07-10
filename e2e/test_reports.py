"""Rapports admin (stats + synthèse LLM) — end-to-end."""

from __future__ import annotations

import httpx
import pytest


def test_reports_forbidden_for_member(api: httpx.Client, new_user: dict) -> None:
    # Un membre normal (non-admin global) ne peut pas générer de rapport.
    r = api.post('/reports/generate', headers=new_user['auth_header'], json={})
    assert r.status_code == 403


def test_reports_admin_generates(api: httpx.Client) -> None:
    # N'exécuté que si un admin global est disponible (compte démo seedé).
    login = api.post(
        '/auth/login',
        json={'email': 'admin@jirou.app', 'password': 'admin_dev_password'},
    )
    if login.status_code != 200:
        pytest.skip("Aucun admin global seedé sur cette instance")
    h = {'Authorization': f"Bearer {login.json()['access_token']}"}

    # Rapport global.
    r = api.post('/reports/generate', headers=h, json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body['markdown'], str) and body['markdown']
    assert 'llm_used' in body
