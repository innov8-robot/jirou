#!/usr/bin/env bash
# ============================================================
# Tests backend (pytest) contre un Postgres JETABLE et ISOLÉ.
# N'utilise jamais la db de l'app (les tests font create_all/drop_all).
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/.."

NAME=jirou-test-db
PORT="${TEST_DB_PORT:-5544}"
export DATABASE_URL="postgresql+psycopg://jirou:jirou_dev_password@localhost:${PORT}/jirou_test"

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup  # au cas où un run précédent aurait laissé un conteneur

echo "[test-backend] Démarrage d'un Postgres jetable ($NAME:$PORT)..."
docker run --rm -d --name "$NAME" \
  -e POSTGRES_USER=jirou \
  -e POSTGRES_PASSWORD=jirou_dev_password \
  -e POSTGRES_DB=jirou_test \
  -p "${PORT}:5432" \
  postgres:16-alpine >/dev/null

echo "[test-backend] Attente de la disponibilité..."
for _ in $(seq 1 30); do
  docker exec "$NAME" pg_isready -U jirou -d jirou_test >/dev/null 2>&1 && break
  sleep 1
done

echo "[test-backend] pytest..."
cd backend && env -u PYTHONPATH DATABASE_URL="$DATABASE_URL" .venv/bin/pytest
