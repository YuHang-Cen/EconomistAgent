#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
RUN_DIR="${ROOT_DIR}/.run"
LOG_DIR="${RUN_DIR}/logs"
BACKEND_PID_FILE="${RUN_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUN_DIR}/frontend.pid"
BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"

DEPLOY_BACKEND_HOST="${DEPLOY_BACKEND_HOST:-127.0.0.1}"
DEPLOY_BACKEND_PORT="${DEPLOY_BACKEND_PORT:-8000}"
DEPLOY_FRONTEND_HOST="${DEPLOY_FRONTEND_HOST:-0.0.0.0}"
DEPLOY_FRONTEND_PORT="${DEPLOY_FRONTEND_PORT:-8081}"
DEPLOY_PUBLIC_URL="${DEPLOY_PUBLIC_URL:-http://202.120.22.16:18181}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] Missing required command: $1"
    exit 1
  fi
}

validate_port() {
  local name="$1"
  local value="$2"
  if [[ ! "${value}" =~ ^[0-9]+$ ]] || (( value < 1 || value > 65535 )); then
    echo "[ERROR] ${name} must be an integer between 1 and 65535."
    exit 1
  fi
}

ensure_env_files() {
  if [[ ! -f "${BACKEND_DIR}/.env" ]]; then
    cp "${BACKEND_DIR}/.env.example" "${BACKEND_DIR}/.env"
    echo "[INFO] Created backend/.env"
  fi
  if [[ ! -f "${FRONTEND_DIR}/.env" ]]; then
    cp "${FRONTEND_DIR}/.env.example" "${FRONTEND_DIR}/.env"
    echo "[INFO] Created frontend/.env"
  fi
}

ensure_port_free() {
  local host="$1"
  local port="$2"
  if ! node - "${host}" "${port}" <<'NODE'
const net = require("node:net");
const host = process.argv[2];
const port = Number(process.argv[3]);
const server = net.createServer();
server.once("error", () => process.exit(1));
server.listen({ host, port }, () => server.close(() => process.exit(0)));
NODE
  then
    echo "[ERROR] Port ${host}:${port} is already in use."
    exit 1
  fi
}

wait_http() {
  local url="$1"
  local timeout_seconds="$2"
  local elapsed=0
  while (( elapsed < timeout_seconds )); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

health_host() {
  case "$1" in
    0.0.0.0|::|"[::]") echo "127.0.0.1" ;;
    *) echo "$1" ;;
  esac
}

check_pid_file() {
  local file="$1"
  local label="$2"
  if [[ ! -f "${file}" ]]; then
    return
  fi
  local pid
  pid="$(sed -n '1p' "${file}")"
  if [[ "${pid}" =~ ^[0-9]+$ ]] && kill -0 "${pid}" >/dev/null 2>&1; then
    echo "[ERROR] ${label} is already running with PID ${pid}."
    exit 1
  fi
  rm -f "${file}"
}

cleanup_failed_start() {
  "${ROOT_DIR}/stop-deploy.sh" >/dev/null 2>&1 || true
}

require_command uv
require_command node
require_command npm
require_command curl
require_command nohup
validate_port DEPLOY_BACKEND_PORT "${DEPLOY_BACKEND_PORT}"
validate_port DEPLOY_FRONTEND_PORT "${DEPLOY_FRONTEND_PORT}"
ensure_env_files
mkdir -p "${LOG_DIR}"
check_pid_file "${BACKEND_PID_FILE}" "Backend"
check_pid_file "${FRONTEND_PID_FILE}" "Frontend"
ensure_port_free "${DEPLOY_BACKEND_HOST}" "${DEPLOY_BACKEND_PORT}"
ensure_port_free "${DEPLOY_FRONTEND_HOST}" "${DEPLOY_FRONTEND_PORT}"

if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  echo "[INFO] Installing frontend dependencies..."
  (cd "${FRONTEND_DIR}" && npm ci)
fi

echo "[INFO] Building frontend..."
(cd "${FRONTEND_DIR}" && npm run build)

echo "[INFO] Starting backend..."
(
  cd "${BACKEND_DIR}"
  if command -v setsid >/dev/null 2>&1; then
    setsid env \
      BACKEND_HOST="${DEPLOY_BACKEND_HOST}" \
      BACKEND_PORT="${DEPLOY_BACKEND_PORT}" \
      uv run serve >"${BACKEND_LOG}" 2>&1 < /dev/null &
  else
    nohup env \
      BACKEND_HOST="${DEPLOY_BACKEND_HOST}" \
      BACKEND_PORT="${DEPLOY_BACKEND_PORT}" \
      uv run serve >"${BACKEND_LOG}" 2>&1 < /dev/null &
  fi
  echo $! >"${BACKEND_PID_FILE}"
)

backend_health_host="$(health_host "${DEPLOY_BACKEND_HOST}")"
if ! wait_http "http://${backend_health_host}:${DEPLOY_BACKEND_PORT}/health" 60; then
  echo "[ERROR] Backend failed to become ready. See ${BACKEND_LOG}"
  cleanup_failed_start
  exit 1
fi

echo "[INFO] Starting frontend..."
(
  cd "${FRONTEND_DIR}"
  if command -v setsid >/dev/null 2>&1; then
    setsid env \
      FRONTEND_HOST="${DEPLOY_FRONTEND_HOST}" \
      FRONTEND_PORT="${DEPLOY_FRONTEND_PORT}" \
      API_ORIGIN="http://${backend_health_host}:${DEPLOY_BACKEND_PORT}" \
      node scripts/serve-static.mjs >"${FRONTEND_LOG}" 2>&1 < /dev/null &
  else
    nohup env \
      FRONTEND_HOST="${DEPLOY_FRONTEND_HOST}" \
      FRONTEND_PORT="${DEPLOY_FRONTEND_PORT}" \
      API_ORIGIN="http://${backend_health_host}:${DEPLOY_BACKEND_PORT}" \
      node scripts/serve-static.mjs >"${FRONTEND_LOG}" 2>&1 < /dev/null &
  fi
  echo $! >"${FRONTEND_PID_FILE}"
)

frontend_health_host="$(health_host "${DEPLOY_FRONTEND_HOST}")"
if ! wait_http "http://${frontend_health_host}:${DEPLOY_FRONTEND_PORT}/__health" 60; then
  echo "[ERROR] Frontend failed to become ready. See ${FRONTEND_LOG}"
  cleanup_failed_start
  exit 1
fi

echo "[OK] EconomistAgent deployment is running."
echo "Frontend local:  http://${frontend_health_host}:${DEPLOY_FRONTEND_PORT}"
echo "Frontend public: ${DEPLOY_PUBLIC_URL}"
echo "Backend health:  http://${backend_health_host}:${DEPLOY_BACKEND_PORT}/health"
echo "Logs: ${LOG_DIR}"
echo "Stop: ./stop-deploy.sh"
