#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT_DIR/backend/.venv"
if [[ ! -x "$VENV/bin/uvicorn" || ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  printf 'Dependencies are missing. Run %s/scripts/setup.sh first.\n' "$ROOT_DIR" >&2
  exit 1
fi

backend_pid=''
frontend_pid=''
# Invoked indirectly by the INT/TERM/EXIT traps.
# shellcheck disable=SC2329
cleanup() {
  trap - INT TERM EXIT
  if [[ -n "$backend_pid" ]] && kill -0 "$backend_pid" 2>/dev/null; then
    kill -TERM -- "-$backend_pid" 2>/dev/null || kill -TERM "$backend_pid" 2>/dev/null || true
  fi
  if [[ -n "$frontend_pid" ]] && kill -0 "$frontend_pid" 2>/dev/null; then
    kill -TERM -- "-$frontend_pid" 2>/dev/null || kill -TERM "$frontend_pid" 2>/dev/null || true
  fi
  if [[ -n "$backend_pid" ]]; then wait "$backend_pid" 2>/dev/null || true; fi
  if [[ -n "$frontend_pid" ]]; then wait "$frontend_pid" 2>/dev/null || true; fi
}
trap cleanup INT TERM EXIT

# Start each server in its own process group so Ctrl-C also stops its children.
# shellcheck disable=SC2016
setsid bash -c 'cd "$1/backend"; env_args=(); [[ -f "$1/.env" ]] && env_args=(--env-file "$1/.env"); exec "$1/backend/.venv/bin/uvicorn" app.main:app "${env_args[@]}" --reload --reload-dir "$1/backend/app" --host 127.0.0.1 --port 8010' _ "$ROOT_DIR" &
backend_pid=$!
# shellcheck disable=SC2016
setsid bash -c 'cd "$1/frontend"; exec npm run dev -- --host 127.0.0.1 --port 5173 --strictPort' _ "$ROOT_DIR" &
frontend_pid=$!

printf 'Backend:  http://127.0.0.1:8010/api/health\nFrontend: http://127.0.0.1:5173\nPress Ctrl-C to stop both servers.\n'

# Wait for either child to stop; then cleanup stops the other one too.
set +e
wait -n "$backend_pid" "$frontend_pid"
status=$?
set -e
exit "$status"
