#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${ROOT_DIR}/.campus-run"
BACKEND_PORT="8000"
FRONTEND_PORT="8081"

has_process_in_group() {
  local pgid="$1"
  ps -eo pgid= | awk -v target="${pgid}" '$1 == target { found = 1 } END { exit(found ? 0 : 1) }'
}

stop_process_group() {
  local label="$1"
  local pgid="$2"

  if ! has_process_in_group "${pgid}"; then
    echo "[INFO] ${label}: process group ${pgid} not running"
    return 0
  fi

  kill -TERM -- "-${pgid}" 2>/dev/null || true
  for _ in $(seq 1 20); do
    if ! has_process_in_group "${pgid}"; then
      echo "[OK] Stopped ${label} process group ${pgid}"
      return 0
    fi
    sleep 0.25
  done

  kill -KILL -- "-${pgid}" 2>/dev/null || true
  for _ in $(seq 1 20); do
    if ! has_process_in_group "${pgid}"; then
      echo "[OK] Force-stopped ${label} process group ${pgid}"
      return 0
    fi
    sleep 0.25
  done

  echo "[WARN] ${label}: process group ${pgid} still has running processes"
  return 1
}

stop_by_port() {
  local label="$1"
  local port="$2"
  local pids

  pids="$(ss -ltnp "( sport = :${port} )" 2>/dev/null | grep -o 'pid=[0-9]\+' | cut -d= -f2 | sort -u || true)"
  if [[ -z "${pids}" ]]; then
    echo "[INFO] ${label}: no listener remains on port ${port}"
    return 0
  fi

  while IFS= read -r pid; do
    [[ -z "${pid}" ]] && continue
    kill -TERM "${pid}" 2>/dev/null || true
  done <<< "${pids}"

  sleep 1

  local remaining
  remaining="$(ss -ltnp "( sport = :${port} )" 2>/dev/null | grep -o 'pid=[0-9]\+' | cut -d= -f2 | sort -u || true)"
  if [[ -n "${remaining}" ]]; then
    while IFS= read -r pid; do
      [[ -z "${pid}" ]] && continue
      kill -KILL "${pid}" 2>/dev/null || true
    done <<< "${remaining}"
  fi

  if ss -ltnH "( sport = :${port} )" | grep -q .; then
    echo "[WARN] ${label}: port ${port} is still occupied"
    return 1
  fi

  echo "[OK] Cleared ${label} listener on port ${port}"
}

stop_by_pid_file() {
  local label="$1"
  local pid_file="$2"

  if [[ ! -f "${pid_file}" ]]; then
    echo "[INFO] ${label}: no pid file"
    return 0
  fi

  local pid
  pid="$(cat "${pid_file}")"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
    stop_process_group "${label}" "${pid}" || true
  else
    echo "[INFO] ${label}: process not running"
  fi
  rm -f "${pid_file}"
}

stop_by_pid_file "backend" "${RUN_DIR}/backend.pid"
stop_by_pid_file "frontend" "${RUN_DIR}/frontend.pid"
stop_by_port "backend" "${BACKEND_PORT}" || true
stop_by_port "frontend" "${FRONTEND_PORT}" || true
