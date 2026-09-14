#!/usr/bin/env bash
set -Eeuo pipefail
set -m

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
BACKEND_PID=""
FRONTEND_PID=""
STOPPING=0

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] Missing required command: $1"
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

stop_group() {
  local pid="$1"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
    kill -TERM -- "-${pid}" >/dev/null 2>&1 || kill -TERM "${pid}" >/dev/null 2>&1 || true
  fi
}

force_stop_group() {
  local pid="$1"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
    kill -KILL -- "-${pid}" >/dev/null 2>&1 || kill -KILL "${pid}" >/dev/null 2>&1 || true
  fi
}

wait_for_stop() {
  local pid="$1"
  local attempt
  [[ -n "${pid}" ]] || return
  for attempt in $(seq 1 20); do
    if ! kill -0 "${pid}" >/dev/null 2>&1; then
      return
    fi
    sleep 0.25
  done
  force_stop_group "${pid}"
}

cleanup() {
  if [[ "${STOPPING}" -eq 1 ]]; then
    return
  fi
  STOPPING=1
  trap - EXIT INT TERM
  echo
  echo "[INFO] Stopping EconomistAgent..."
  stop_group "${FRONTEND_PID}"
  stop_group "${BACKEND_PID}"
  wait_for_stop "${FRONTEND_PID}"
  wait_for_stop "${BACKEND_PID}"
  [[ -z "${FRONTEND_PID}" ]] || wait "${FRONTEND_PID}" 2>/dev/null || true
  [[ -z "${BACKEND_PID}" ]] || wait "${BACKEND_PID}" 2>/dev/null || true
  echo "[OK] EconomistAgent stopped."
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

require_command uv
require_command node
require_command npm
require_command curl
ensure_env_files
ensure_port_free "127.0.0.1" "8000"
ensure_port_free "0.0.0.0" "3000"

if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  echo "[INFO] Installing frontend dependencies..."
  (cd "${FRONTEND_DIR}" && npm ci)
fi

echo "[INFO] Starting backend with hot reload..."
(cd "${BACKEND_DIR}" && exec uv run dev) &
BACKEND_PID=$!

if ! wait_http "http://127.0.0.1:8000/health" 60; then
  echo "[ERROR] Backend failed to become ready."
  exit 1
fi

echo "[INFO] Starting frontend with hot reload..."
(cd "${FRONTEND_DIR}" && exec npm run dev) &
FRONTEND_PID=$!

if ! wait_http "http://127.0.0.1:3000" 60; then
  echo "[ERROR] Frontend failed to become ready."
  exit 1
fi

echo
echo "[OK] EconomistAgent is running."
echo "Frontend: http://127.0.0.1:3000"
echo "Backend:  http://127.0.0.1:8000/health"
echo "Press Ctrl+C to stop both services."

while kill -0 "${BACKEND_PID}" >/dev/null 2>&1 && kill -0 "${FRONTEND_PID}" >/dev/null 2>&1; do
  sleep 1
done

echo "[ERROR] A service exited unexpectedly."
exit 1
