#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up --build -d --wait
docker compose exec -T web flask --app app seed-documents
mkdir -p keys
if [ ! -f keys/elena-private.pem ] && [ ! -f keys/elena-public.pem ]; then
  bash tools/firma-local.sh crear-clave elena-private.pem elena-public.pem
fi
docker compose cp keys/elena-public.pem web:/tmp/elena-public.pem
docker compose exec -T web flask --app app register-signing-key elena /tmp/elena-public.pem
echo "Portal preparado: http://localhost:8002"
