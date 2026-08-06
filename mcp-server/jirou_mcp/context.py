"""Client Jirou de la requête en cours (transport HTTP).

Module volontairement minuscule et sans dépendance interne : il est importé à la
fois par :mod:`jirou_mcp.server` (qui lit le client) et par
:mod:`jirou_mcp.http` (qui le pose), ce qui interdit de le loger dans l'un des
deux — ce serait un import circulaire.

En mode **stdio**, rien ne pose ce contexte : le client vient de
l'environnement. En mode **HTTP**, le middleware d'authentification le pose pour
la durée de la requête, à partir du jeton porté par l'en-tête ``Authorization``.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - uniquement pour le typage
    from jirou_mcp.client import JirouClient

_request_client: ContextVar[JirouClient | None] = ContextVar("jirou_request_client", default=None)


def current_client() -> JirouClient | None:
    """Client de la requête HTTP en cours, ou ``None`` hors contexte HTTP."""
    return _request_client.get()


def set_current_client(client: JirouClient) -> Token:
    """Associe un client à la requête en cours ; à libérer avec :func:`reset`."""
    return _request_client.set(client)


def reset(token: Token) -> None:
    """Libère le client posé par :func:`set_current_client`."""
    _request_client.reset(token)
