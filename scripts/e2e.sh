#!/usr/bin/env bash
# ============================================================
# Lance la suite e2e contre la stack Jirou.
# - démarre la stack si elle ne tourne pas (KEEP_UP=1 pour la laisser après)
# - attend que le backend soit healthy
# - exécute pytest e2e/
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/.."

API_BASE_URL="${API_BASE_URL:-http://localhost:8010}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:5199}"
STARTED=0

started_by_us() { [ "$STARTED" = "1" ] && [ "${KEEP_UP:-0}" != "1" ]; }
cleanup() { started_by_us && docker compose down || true; }
trap cleanup EXIT

# Démarre la stack si le backend ne répond pas déjà.
if ! curl -sf "$API_BASE_URL/health" >/dev/null 2>&1; then
  echo "[e2e] Démarrage de la stack..."
  [ -f .env ] || cp .env.example .env
  docker compose up -d --build
  STARTED=1
fi

echo "[e2e] Attente du backend ($API_BASE_URL/health)..."
for _ in $(seq 1 60); do
  if curl -sf "$API_BASE_URL/health" >/dev/null 2>&1; then
    echo "[e2e] Backend prêt."
    break
  fi
  sleep 2
done

# Environnement Python pour les tests e2e.
PYTEST_BIN="python3 -m pytest"
if [ -d e2e/.venv ]; then
  PYTEST_BIN="e2e/.venv/bin/python -m pytest"
fi

echo "[e2e] Exécution des tests..."
API_BASE_URL="$API_BASE_URL" FRONTEND_URL="$FRONTEND_URL" \
  env -u PYTHONPATH $PYTEST_BIN e2e/ -v
