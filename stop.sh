#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! docker compose version >/dev/null 2>&1; then
  echo "[ERROR] Docker Compose is not available."
  exit 1
fi

cd "${ROOT_DIR}"
docker compose down

echo "[OK] Services stopped."
