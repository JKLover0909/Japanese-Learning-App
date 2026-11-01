#!/usr/bin/env bash
# Runs every validation gate: backend tests, lint, content and audio checks, then frontend tests,
# type check and lint. Usage: scripts/check.sh [backend|frontend] [--build]
set -uo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT_DIR/backend/.venv/bin/python"
BIN="$ROOT_DIR/frontend/node_modules/.bin"
scope=all
build=false
for arg in "$@"; do
  case "$arg" in
    backend | frontend) scope=$arg ;;
    --build) build=true ;;
    *) printf 'Usage: %s [backend|frontend] [--build]\n' "$0" >&2; exit 64 ;;
  esac
done

failed=()
run() {
  local name=$1 dir=$2
  shift 2
  printf '\n== %s\n' "$name"
  if (cd "$ROOT_DIR/$dir" && "$@"); then printf -- '-- %s: ok\n' "$name"; else failed+=("$name"); fi
}

if [[ $scope != frontend ]]; then
  [[ -x "$PY" ]] || { printf 'Missing backend/.venv. Run scripts/setup.sh first.\n' >&2; exit 1; }
  run pytest backend "$PY" -m pytest -q -p no:warnings
  run ruff backend "$PY" -m ruff check .
  run validate_content backend "$PY" scripts/validate_content.py
  run audio_manifest backend "$PY" scripts/generate_audio.py --check
fi
if [[ $scope != backend ]]; then
  [[ -x "$BIN/vitest" ]] || { printf 'Missing frontend/node_modules. Run scripts/setup.sh first.\n' >&2; exit 1; }
  run vitest frontend "$BIN/vitest" run
  run tsc frontend "$BIN/tsc" -b
  run eslint frontend "$BIN/eslint" .
  if $build; then run vite_build frontend "$BIN/vite" build; fi
fi

if ((${#failed[@]})); then
  printf '\nFAILED: %s\n' "${failed[*]}"
  exit 1
fi
printf '\nAll checks passed.\n'
