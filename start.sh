#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ROOT_DIR}/backend/.env"
ENV_EXAMPLE="${ROOT_DIR}/backend/.env.example"
STORAGE_DIR="${ROOT_DIR}/backend/storage"

if ! docker compose version >/dev/null 2>&1; then
  echo "[ERROR] Docker Compose is not available. Please install Docker Desktop first."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "[ERROR] Docker daemon is not running. Please start Docker Desktop first."
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ ! -f "${ENV_EXAMPLE}" ]]; then
    echo "[ERROR] Missing backend/.env.example"
    exit 1
  fi
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
  echo "[INFO] Created backend/.env from backend/.env.example"
fi

mkdir -p "${STORAGE_DIR}"

cd "${ROOT_DIR}"
docker compose up -d --build

echo "[OK] Services started."
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000/health"
echo "Redis:    localhost:6379"
