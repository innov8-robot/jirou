#!/usr/bin/env bash
# Construit le frontend Jirou et le déploie dans le dossier servi par Caddy.
# À relancer à chaque mise à jour du frontend :  bash deploy-frontend.sh
set -euo pipefail
cd "$(dirname "$0")"

VITE_API_URL="$(grep -E '^VITE_API_URL=' .env | cut -d= -f2-)"
WEBROOT="/var/www/jirou.innov9.fr"

echo ">> Build du frontend (VITE_API_URL=$VITE_API_URL)"
docker build \
  --build-arg "VITE_API_URL=$VITE_API_URL" \
  -f frontend/Dockerfile.prod \
  -t jirou-frontend-build \
  ./frontend

echo ">> Extraction des fichiers statiques vers $WEBROOT"
cid="$(docker create jirou-frontend-build)"
rm -rf "$WEBROOT"
mkdir -p "$WEBROOT"
docker cp "$cid:/app/dist/." "$WEBROOT/"
docker rm "$cid" >/dev/null
chmod -R a+rX "$WEBROOT"

echo ">> OK. Contenu déployé :"
ls -la "$WEBROOT"
