#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT_DIR/backend/.venv"
if [[ ! -x "$VENV/bin/uvicorn" || ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  printf 'Dependencies are missing. Run %s/scripts/setup.sh first.\n' "$ROOT_DIR" >&2
  exit 1
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8010}"
case "$PORT" in
  ''|*[!0-9]*) printf 'PORT must be an integer from 1 to 65535.\n' >&2; exit 1 ;;
esac
if (( PORT < 1 || PORT > 65535 )); then
  printf 'PORT must be an integer from 1 to 65535.\n' >&2
  exit 1
fi

# Set HOST=0.0.0.0 for access from a phone on the same LAN.
cd "$ROOT_DIR/frontend"
npm run build
cd "$ROOT_DIR/backend"
# Optional untracked secrets/settings (e.g. the admin password hash); uvicorn rejects a missing file.
env_args=()
[[ -f "$ROOT_DIR/.env" ]] && env_args=(--env-file "$ROOT_DIR/.env")
exec "$VENV/bin/uvicorn" app.main:app \
  "${env_args[@]}" \
  --host "$HOST" \
  --port "$PORT" \
  --proxy-headers \
  --forwarded-allow-ips 127.0.0.1
