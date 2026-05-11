#!/usr/bin/env bash
set -euo pipefail

if [ ! -d gepa/pids ]; then
  echo "No gepa/pids directory found."
  exit 0
fi

for pid_file in gepa/pids/*.pid; do
  [ -e "${pid_file}" ] || continue
  pid="$(cat "${pid_file}")"
  role="$(basename "${pid_file}" .pid)"
  if kill -0 "${pid}" 2>/dev/null; then
    echo "Stopping ${role} (${pid})"
    kill "${pid}" 2>/dev/null || true
  fi
done

sleep 5

for pid_file in gepa/pids/*.pid; do
  [ -e "${pid_file}" ] || continue
  pid="$(cat "${pid_file}")"
  role="$(basename "${pid_file}" .pid)"
  if kill -0 "${pid}" 2>/dev/null; then
    echo "Force-stopping ${role} (${pid})"
    kill -9 "${pid}" 2>/dev/null || true
  fi
  rm -f "${pid_file}"
done
