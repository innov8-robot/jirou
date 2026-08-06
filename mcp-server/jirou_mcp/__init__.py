"""Serveur MCP pour Jirou — expose tickets, sprints, veille et docs à un agent.

Point d'entrée : ``jirou-mcp`` (ou ``python -m jirou_mcp``), qui sert le
protocole MCP sur stdio. Cf. le README pour la configuration côté Claude Code.
"""

from __future__ import annotations

from jirou_mcp.client import JirouClient, JirouError

__all__ = ["JirouClient", "JirouError", "main"]

__version__ = "0.1.0"


def main() -> None:
    """Lance le serveur MCP (import différé : évite de charger le SDK trop tôt)."""
    from jirou_mcp.server import main as _main

    _main()
