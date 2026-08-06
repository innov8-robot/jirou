"""Transport HTTP du serveur MCP, pour un client distant (Claude Code sur un poste).

Le mode stdio (:mod:`jirou_mcp.server`) suppose que le client lance le serveur, donc
qu'ils sont sur la même machine. Ici le serveur tourne en service sur le VPS et
le client l'atteint en HTTPS via Caddy.

Ce changement de transport déplace la question de l'authentification : en stdio,
le jeton vient de l'environnement que le client contrôle ; en HTTP, l'endpoint
est joignable par n'importe qui et doit donc s'authentifier lui-même.

**Le jeton est fourni par requête, par le client**, dans l'en-tête
``Authorization: Bearer jir_pat_…`` — celui-là même qu'on créerait pour le mode
stdio. Conséquences voulues :

- **aucun second secret** : pas de clé d'API du serveur MCP à gérer, à faire
  tourner ou à fuiter. Le seul identifiant est le jeton Jirou, déjà révocable
  depuis l'interface ;
- **aucune identité par défaut** : le serveur n'a pas de jeton à lui, donc une
  requête non authentifiée ne peut rien lire. C'est ce qui rend l'exposition
  publique acceptable ;
- **jeton vérifié au niveau HTTP** : le middleware appelle ``/auth/me`` la
  première fois qu'il voit un jeton et renvoie 401 s'il est invalide, plutôt que
  de laisser chaque outil échouer plus loin.

Le middleware est du **pur ASGI** et non un ``BaseHTTPMiddleware`` : ce dernier
casse les réponses en flux, or le transport streamable-http peut répondre en SSE.
"""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from collections.abc import Awaitable, Callable

from mcp.server.transport_security import TransportSecuritySettings

from jirou_mcp import context
from jirou_mcp.client import JirouClient, JirouError
from jirou_mcp.server import mcp

# Chemin servi par le transport streamable-http (aligné sur le défaut du SDK).
MCP_PATH = "/mcp"

# Sonde de vie, volontairement hors authentification : sert à vérifier que le
# service tourne (systemd, Caddy, curl) sans avoir à exhiber un jeton.
HEALTH_PATH = "/healthz"

# Client par jeton : conserve la réutilisation de connexion et les caches de
# résolution entre requêtes. Borné, pour qu'une rafale de faux jetons ne fasse
# pas grossir la mémoire indéfiniment.
_MAX_CLIENTS = 8

Scope = dict
Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]


class _ClientPool:
    """Clients Jirou indexés par jeton, validés une fois, bornés en nombre."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self._clients: OrderedDict[str, JirouClient] = OrderedDict()

    def get(self, token: str) -> JirouClient:
        """Retourne un client validé pour ce jeton.

        Lève :class:`JirouError` si le jeton est refusé par l'API — le premier
        appel vérifie via ``/auth/me``, les suivants réutilisent le client.
        """
        existing = self._clients.get(token)
        if existing is not None:
            self._clients.move_to_end(token)
            return existing

        client = JirouClient(self._base_url, token)
        try:
            client.get("/auth/me")
        except JirouError:
            client.close()
            raise

        self._clients[token] = client
        while len(self._clients) > _MAX_CLIENTS:
            _, evicted = self._clients.popitem(last=False)
            evicted.close()
        return client


async def _json_response(send: Send, status: int, detail: str, *, challenge: bool = False) -> None:
    """Émet une réponse JSON ``{"detail": ...}`` (forme d'erreur de l'API Jirou)."""
    body = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
    headers = [(b"content-type", b"application/json; charset=utf-8")]
    if challenge:
        headers.append((b"www-authenticate", b"Bearer"))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class RequireJirouToken:
    """Middleware ASGI : exige un jeton Jirou valide et l'expose aux outils.

    Répond 200 sur :data:`HEALTH_PATH` sans authentification, 401 sur toute autre
    requête dépourvue d'un ``Authorization: Bearer jir_pat_…`` accepté par l'API.
    """

    def __init__(self, app: Callable, pool: _ClientPool) -> None:
        self._app = app
        self._pool = pool

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        if scope.get("path") == HEALTH_PATH:
            await _json_response(send, 200, "ok")
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        raw = headers.get(b"authorization", b"").decode("latin-1")
        token = raw[len("Bearer ") :].strip() if raw.lower().startswith("bearer ") else ""

        if not token.startswith("jir_pat_"):
            await _json_response(
                send,
                401,
                "Jeton d'API Jirou requis dans l'en-tête « Authorization: Bearer jir_pat_… ». "
                "Créez-en un dans Jirou → Mon profil → Jetons d'API.",
                challenge=True,
            )
            return

        try:
            client = self._pool.get(token)
        except JirouError as exc:
            await _json_response(send, 401, str(exc), challenge=True)
            return

        token_ref = context.set_current_client(client)
        try:
            await self._app(scope, receive, send)
        finally:
            context.reset(token_ref)


def build_app(base_url: str, allowed_hosts: list[str] | None = None):  # noqa: ANN201 - Starlette
    """Construit l'application ASGI : transport MCP derrière l'authentification.

    ``stateless_http=True`` : chaque requête est traitée isolément, sans session
    conservée entre appels. C'est ce qui convient au modèle « un jeton par
    requête » et garantit que l'outil s'exécute dans le contexte de la requête
    qui a porté le jeton.

    ``allowed_hosts`` alimente la protection anti-DNS-rebinding du SDK, qui
    valide l'en-tête ``Host`` et répond **421** à un hôte inconnu. Derrière un
    reverse-proxy, ``Host`` est le nom public : il doit figurer dans la liste,
    sinon rien ne passe. On garde la protection active plutôt que de la
    désactiver — c'est elle qui empêche un site tiers de faire parler ce service
    via le navigateur de la victime.
    """
    hosts = list(allowed_hosts or _default_allowed_hosts())
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        # Les clients MCP hors navigateur n'envoient pas d'``Origin`` ; on
        # autorise les origines correspondant aux hôtes admis, pas plus.
        allowed_origins=[f"https://{h}" for h in hosts] + [f"http://{h}" for h in hosts],
    )
    app = mcp.streamable_http_app(
        streamable_http_path=MCP_PATH,
        stateless_http=True,
        transport_security=security,
    )
    return RequireJirouToken(app, _ClientPool(base_url))


def _default_allowed_hosts() -> list[str]:
    """Hôtes admis par défaut : ``JIROU_MCP_ALLOWED_HOSTS`` + la boucle locale."""
    configured = [
        h.strip() for h in (os.environ.get("JIROU_MCP_ALLOWED_HOSTS") or "").split(",") if h.strip()
    ]
    return configured + ["127.0.0.1", "localhost"]


def main() -> None:
    """Point d'entrée du service HTTP (``jirou-mcp-http``).

    Configuration : ``JIROU_API_URL`` (obligatoire), ``JIROU_MCP_ALLOWED_HOSTS``
    (le nom public servi par le reverse-proxy, sans quoi le SDK répond 421),
    ``JIROU_MCP_HOST`` et ``JIROU_MCP_PORT`` (défaut ``127.0.0.1:8012`` —
    l'exposition publique est le rôle du reverse-proxy, pas du service).
    ``JIROU_TOKEN`` n'est **pas** lu : en HTTP le jeton vient du client.
    """
    import uvicorn

    base_url = (os.environ.get("JIROU_API_URL") or "").strip()
    if not base_url:
        raise SystemExit("JIROU_API_URL est obligatoire (ex. http://127.0.0.1:8011).")

    uvicorn.run(
        build_app(base_url),
        host=os.environ.get("JIROU_MCP_HOST", "127.0.0.1"),
        port=int(os.environ.get("JIROU_MCP_PORT", "8012")),
        log_level=os.environ.get("JIROU_MCP_LOG_LEVEL", "info"),
        access_log=False,
    )
