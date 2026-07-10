"""Le frontend est servi et c'est bien l'app Jirou."""

from __future__ import annotations

import httpx


def test_frontend_served(frontend_url: str) -> None:
    r = httpx.get(frontend_url, timeout=10.0)
    assert r.status_code == 200
    assert "<title>Jirou</title>" in r.text
