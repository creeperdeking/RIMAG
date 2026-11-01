#!/usr/bin/env bash
# Open the OpenMC model currently stored in runs/default with openmc-plotter.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/runs/default"
PLOTTER="${OPENMC_PLOTTER:-$HOME/miniforge3/envs/openmc-plot/bin/openmc-plotter}"

# Docker receives this path as /data. The plotter runs in WSL, so it needs the same file directly.
to_wsl_path() {
  local path="$1"
  path="${path//\\//}"
  path="${path%$'\r'}"
  if [[ "$path" =~ ^[A-Za-z]:/ ]]; then
    local drive="${path:0:1}"
    drive="${drive,,}"
    printf '/mnt/%s/%s' "$drive" "${path:3}"
  else
    printf '%s' "$path"
  fi
}

if [[ -z "${OPENMC_CROSS_SECTIONS:-}" ]]; then
  if [[ ! -f "$ROOT/.env" ]]; then
    echo "OPENMC_CROSS_SECTIONS n'est pas défini et $ROOT/.env est introuvable." >&2
    exit 1
  fi
  DATA_DIR="$(grep -E '^OPENMC_DATA_DIR=' "$ROOT/.env" | tail -n 1 || true)"
  DATA_DIR="${DATA_DIR#OPENMC_DATA_DIR=}"
  DATA_DIR="${DATA_DIR#\"}"
  DATA_DIR="${DATA_DIR%\"}"
  DATA_DIR="${DATA_DIR#\'}"
  DATA_DIR="${DATA_DIR%\'}"
  if [[ -z "$DATA_DIR" ]]; then
    echo "OPENMC_DATA_DIR est absent de $ROOT/.env." >&2
    exit 1
  fi
  OPENMC_CROSS_SECTIONS="$(to_wsl_path "$DATA_DIR")/cross_sections.xml"
  export OPENMC_CROSS_SECTIONS
fi

if [[ ! -f "$OPENMC_CROSS_SECTIONS" ]]; then
  echo "Fichier de sections efficaces introuvable :" >&2
  echo "  $OPENMC_CROSS_SECTIONS" >&2
  exit 1
fi

if [[ ! -f "$RUN_DIR/geometry.xml" || ! -f "$RUN_DIR/materials.xml" ]]; then
  echo "geometry.xml et materials.xml sont absents de :" >&2
  echo "  $RUN_DIR" >&2
  echo "Générez-les d'abord avec un run en mode render, par exemple :" >&2
  echo "  docker compose run --rm rimag python simulation_paper.py my_params.json" >&2
  exit 1
fi

if [[ ! -x "$PLOTTER" ]]; then
  echo "openmc-plotter est introuvable : $PLOTTER" >&2
  exit 1
fi

# OpenMC rewrites summary.h5 in the model directory. The copy in runs/default
# is created by the container and is not writable from WSL, so stage the XML here.
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/rimag-geometry.XXXXXX")"
cleanup() {
  rm -rf "$STAGE"
}
trap cleanup EXIT
for name in geometry.xml materials.xml settings.xml plots.xml; do
  if [[ -f "$RUN_DIR/$name" ]]; then
    cp "$RUN_DIR/$name" "$STAGE/"
  fi
done

echo "Ouverture de la géométrie dans $RUN_DIR"
echo "Sections efficaces : $OPENMC_CROSS_SECTIONS"
"$PLOTTER" "$STAGE"
