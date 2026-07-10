#!/usr/bin/env bash
# Entrypoint du conteneur backend : applique les migrations puis démarre l'API.
set -euo pipefail

echo "[entrypoint] Application des migrations Alembic (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] Démarrage : $*"
exec "$@"
