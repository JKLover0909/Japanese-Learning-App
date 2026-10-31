#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  printf 'Python executable not found: %s\n' "$PYTHON" >&2
  exit 1
fi
if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  printf 'Python 3.11 or newer is required.\n' >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  printf 'npm is required. Install Node.js 20 or newer, then retry.\n' >&2
  exit 1
fi
if ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 20 ? 0 : 1)'; then
  printf 'Node.js 20 or newer is required.\n' >&2
  exit 1
fi

VENV="$ROOT_DIR/backend/.venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -e "$ROOT_DIR/backend[dev]"

cd "$ROOT_DIR/frontend"
npm install

printf '\nSetup complete. Start the app with %s/scripts/dev.sh\n' "$ROOT_DIR"
