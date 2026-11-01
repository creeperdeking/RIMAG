#!/usr/bin/env bash
# Rebuild the RIMAG image from the files currently in this repository.
# --no-cache forces Docker to copy the working tree again instead of reusing a layer.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -f docker-compose.yml ]]; then
  echo "docker-compose.yml introuvable dans $ROOT" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Fichier .env introuvable dans $ROOT. OPENMC_DATA_DIR doit y être défini." >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  DOCKER=(docker)
elif docker.exe compose version >/dev/null 2>&1; then
  DOCKER=(docker.exe)
else
  echo "Docker Compose est introuvable. Démarrez Docker Desktop, puis relancez ce script." >&2
  exit 1
fi

echo "Reconstruction sans cache de rimag:research-paper"
echo "Sources : $ROOT"
"${DOCKER[@]}" compose build --no-cache
echo "Image reconstruite : rimag:research-paper"
