#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${ROOT_DIR}/.run"

child_pids() {
  local parent="$1"
  ps -eo pid=,ppid= | awk -v parent="${parent}" '$2 == parent { print $1 }'
}

collect_tree() {
  local parent="$1"
  local child
  while IFS= read -r child; do
    [[ -z "${child}" ]] && continue
    collect_tree "${child}"
    echo "${child}"
  done < <(child_pids "${parent}")
}

stop_from_pid_file() {
  local label="$1"
  local file="$2"
  if [[ ! -f "${file}" ]]; then
    echo "[INFO] ${label}: no PID file"
    return
  fi

  local pid descendants
  pid="$(sed -n '1p' "${file}")"
  if [[ ! "${pid}" =~ ^[0-9]+$ ]] || ! kill -0 "${pid}" >/dev/null 2>&1; then
    echo "[INFO] ${label}: process is not running"
    rm -f "${file}"
    return
  fi

  descendants="$(collect_tree "${pid}")"
  if [[ -n "${descendants}" ]]; then
    # shellcheck disable=SC2086
    kill -TERM ${descendants} >/dev/null 2>&1 || true
  fi
  kill -TERM "${pid}" >/dev/null 2>&1 || true

  for _ in $(seq 1 20); do
    if ! kill -0 "${pid}" >/dev/null 2>&1; then
      rm -f "${file}"
      echo "[OK] Stopped ${label}"
      return
    fi
    sleep 0.25
  done

  if [[ -n "${descendants}" ]]; then
    # shellcheck disable=SC2086
    kill -KILL ${descendants} >/dev/null 2>&1 || true
  fi
  kill -KILL "${pid}" >/dev/null 2>&1 || true
  rm -f "${file}"
  echo "[OK] Force-stopped ${label}"
}

stop_from_pid_file "frontend" "${RUN_DIR}/frontend.pid"
stop_from_pid_file "backend" "${RUN_DIR}/backend.pid"
