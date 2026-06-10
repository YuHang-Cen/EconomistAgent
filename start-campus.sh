#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
RUN_DIR="${ROOT_DIR}/.campus-run"
LOG_DIR="${RUN_DIR}/logs"

BACKEND_PID_FILE="${RUN_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUN_DIR}/frontend.pid"
BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"
BACKEND_ENV_FILE="${BACKEND_DIR}/.env"
FRONTEND_ENV_FILE="${FRONTEND_DIR}/.env"

BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8000"
FRONTEND_HOST="0.0.0.0"
FRONTEND_PORT="8081"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] Missing required command: $1"
    exit 1
  fi
}

ensure_port_free() {
  local port="$1"
  local address="$2"
  if ss -ltnH "( sport = :${port} )" | grep -q .; then
    echo "[ERROR] Port ${port} is already in use. Please stop the existing service first."
    exit 1
  fi
  echo "[INFO] Port ${port} is available for ${address}"
}

wait_http() {
  local url="$1"
  local timeout_seconds="$2"
  local elapsed=0

  while (( elapsed < timeout_seconds )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done

  return 1
}

get_env_file_value() {
  local file="$1"
  local key="$2"

  if [[ ! -f "${file}" ]]; then
    return 0
  fi

  awk -F= -v target="${key}" '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    $1 == target {
      sub(/^[^=]*=/, "", $0)
      print $0
      exit
    }
  ' "${file}"
}

start_backend() {
  echo "[INFO] Starting backend on ${BACKEND_HOST}:${BACKEND_PORT}"
  (
    cd "${BACKEND_DIR}"
    if [[ ! -f "${BACKEND_ENV_FILE}" ]]; then
      cp .env.example .env
      echo "[INFO] Created backend/.env from backend/.env.example"
    fi
    setsid bash -lc \
      "exec uv run --python 3.11 serve" \
      >"${BACKEND_LOG}" 2>&1 < /dev/null &
    echo $! > "${BACKEND_PID_FILE}"
  )

  if ! wait_http "http://${BACKEND_HOST}:${BACKEND_PORT}/health" 30; then
    echo "[ERROR] Backend failed to become ready. Check ${BACKEND_LOG}"
    exit 1
  fi
  echo "[OK] Backend is ready at http://${BACKEND_HOST}:${BACKEND_PORT}/health"
}

start_frontend() {
  echo "[INFO] Building frontend"
  (
    cd "${FRONTEND_DIR}"
    if [[ ! -d node_modules ]]; then
      npm ci
    fi
    if [[ ! -f "${FRONTEND_ENV_FILE}" ]]; then
      cp .env.example .env
      echo "[INFO] Created frontend/.env from frontend/.env.example"
    fi
    local analysis_only
    analysis_only="$(get_env_file_value "${BACKEND_ENV_FILE}" "VITE_UI_ANALYSIS_ONLY")"
    if [[ -z "${analysis_only}" ]]; then
      analysis_only="$(get_env_file_value "${FRONTEND_ENV_FILE}" "VITE_UI_ANALYSIS_ONLY")"
    fi
    if [[ -z "${analysis_only}" ]]; then
      analysis_only="false"
    fi
    echo "[INFO] Frontend VITE_UI_ANALYSIS_ONLY=${analysis_only}"
    env VITE_UI_ANALYSIS_ONLY="${analysis_only}" npm run build
    echo "[INFO] Starting frontend on ${FRONTEND_HOST}:${FRONTEND_PORT}"
    setsid env \
      CAMPUS_HOST="${FRONTEND_HOST}" \
      CAMPUS_PORT="${FRONTEND_PORT}" \
      CAMPUS_API_ORIGIN="http://${BACKEND_HOST}:${BACKEND_PORT}" \
      node scripts/campus-server.mjs \
      >"${FRONTEND_LOG}" 2>&1 < /dev/null &
    echo $! > "${FRONTEND_PID_FILE}"
  )

  if ! wait_http "http://127.0.0.1:${FRONTEND_PORT}/__campus_health" 30; then
    echo "[ERROR] Frontend failed to become ready. Check ${FRONTEND_LOG}"
    exit 1
  fi
  echo "[OK] Frontend is ready at http://127.0.0.1:${FRONTEND_PORT}"
}

require_command uv
require_command node
require_command npm
require_command ss
require_command curl
require_command setsid

mkdir -p "${LOG_DIR}"

ensure_port_free "${BACKEND_PORT}" "backend"
ensure_port_free "${FRONTEND_PORT}" "frontend"

start_backend
start_frontend

cat <<EOF
[DONE] Campus deployment is running.
Frontend local:  http://127.0.0.1:${FRONTEND_PORT}
Frontend campus: http://202.120.22.16:18181
Backend local:   http://${BACKEND_HOST}:${BACKEND_PORT}/health

Logs:
  ${BACKEND_LOG}
  ${FRONTEND_LOG}

Stop:
  ./stop-campus.sh
EOF
