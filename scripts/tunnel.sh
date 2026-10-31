#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-ngrok}"
PORT="${PORT:-8010}"
# Only check whether the admin login is configured; never print its values.
admin_configured=false
if [[ -n "${JP_ADMIN_USERNAME:-}" && -n "${JP_ADMIN_PASSWORD_HASH:-}" ]]; then
  admin_configured=true
elif [[ -f "$ROOT_DIR/.env" ]] \
  && grep -qE "^JP_ADMIN_USERNAME=['\"]?[^'\"[:space:]]" "$ROOT_DIR/.env" \
  && grep -qE "^JP_ADMIN_PASSWORD_HASH=['\"]?[^'\"[:space:]]" "$ROOT_DIR/.env"; then
  admin_configured=true
fi
if [[ "$admin_configured" != true ]]; then
  printf 'NOTE: the admin statistics login is not configured, so /admin will refuse sign-in. Run backend/scripts/set_admin_password.py and restart serve.sh.\n' >&2
fi
case "$PORT" in
  ''|*[!0-9]*) printf 'PORT must be an integer from 1 to 65535.\n' >&2; exit 1 ;;
esac
if (( PORT < 1 || PORT > 65535 )); then
  printf 'PORT must be an integer from 1 to 65535.\n' >&2
  exit 1
fi

if [[ "$MODE" == 'ngrok' ]]; then
  if [[ -x /snap/bin/ngrok ]]; then
    NGROK=/snap/bin/ngrok
  elif command -v ngrok >/dev/null 2>&1; then
    NGROK="$(command -v ngrok)"
  else
    printf 'ngrok not found. Install it, then run: ngrok config add-authtoken <token>\n' >&2
    exit 1
  fi
  if ! "$NGROK" config check >/dev/null 2>&1; then
    printf 'ngrok is not configured. Run: %s config add-authtoken <token>\n' "$NGROK" >&2
    exit 1
  fi
  printf 'Starting ngrok for http://127.0.0.1:%s\n' "$PORT"
  printf 'Keep %s/scripts/serve.sh running in another terminal.\n' "$ROOT_DIR"
  exec "$NGROK" http "127.0.0.1:$PORT"
elif [[ "$MODE" == 'cloudflare' ]]; then
  if command -v cloudflared >/dev/null 2>&1; then
    CLOUDFLARED="$(command -v cloudflared)"
  elif [[ -x /usr/local/bin/cloudflared ]]; then
    CLOUDFLARED=/usr/local/bin/cloudflared
  else
    printf 'cloudflared not found. Install cloudflared or use Docker Compose profile "tunnel".\n' >&2
    exit 1
  fi
  printf 'Starting a temporary Cloudflare quick tunnel for http://127.0.0.1:%s\n' "$PORT"
  printf 'Keep %s/scripts/serve.sh running in another terminal.\n' "$ROOT_DIR"
  exec "$CLOUDFLARED" tunnel --url "http://127.0.0.1:$PORT"
else
  printf 'Usage: %s [ngrok|cloudflare]\n' "${BASH_SOURCE[0]}" >&2
  exit 2
fi
