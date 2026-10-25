#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p keys
image_id="$(docker compose images -q web | head -n 1)"
if [ -z "$image_id" ]; then
  echo "Construye primero: docker compose build web" >&2
  exit 1
fi
interactive=(-i)
if [ -t 0 ]; then interactive=(-it); fi
docker run --rm "${interactive[@]}" --network none \
  --user "$(id -u):$(id -g)" -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$PWD/keys:/signing" -w /signing \
  "$image_id" python /portal/tools/firma.py "$@"
