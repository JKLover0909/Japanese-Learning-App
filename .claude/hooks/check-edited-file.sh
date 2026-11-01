#!/usr/bin/env bash
# PostToolUse check after Edit/Write: lints the edited Python or TypeScript file and validates
# lesson JSON. Problems go back to Claude on stderr (exit 2); nothing is rewritten.
set -uo pipefail

ROOT=${CLAUDE_PROJECT_DIR:-$PWD}
path=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty')
[[ -n "$path" && -f "$path" ]] || exit 0
rel=${path#"$ROOT"/}
python="$ROOT/backend/.venv/bin/python"
eslint="$ROOT/frontend/node_modules/.bin/eslint"

report() {
  printf '%s\n%s\n' "$1" "$2" >&2
  exit 2
}

case "$rel" in
  backend/*.py)
    [[ -x "$python" ]] || exit 0
    out=$(cd "$ROOT/backend" && "$python" -m ruff check --no-fix --quiet "$path" 2>&1) \
      || report "ruff found problems in $rel:" "$out"
    ;;
  frontend/*.ts | frontend/*.tsx)
    [[ -x "$eslint" ]] || exit 0
    out=$(cd "$ROOT/frontend" && "$eslint" --no-warn-ignored "$path" 2>&1) \
      || report "eslint found problems in $rel:" "$out"
    ;;
  backend/app/content/lessons/*.json)
    [[ -x "$python" ]] || exit 0
    out=$(cd "$ROOT/backend" && "$python" scripts/validate_content.py 2>&1) \
      || report "validate_content.py failed after editing $rel:" "$(tail -n 40 <<<"$out")"
    # Published keys must never be renamed or reused: list keys that disappeared since HEAD.
    if before=$(git -C "$ROOT" show "HEAD:$rel" 2>/dev/null); then
      removed=$(comm -23 <(jq -r '.items[].key' <<<"$before" | sort) <(jq -r '.items[].key' "$path" | sort))
      [[ -z "$removed" ]] || report "Keys removed from $rel since HEAD. Removed items become inactive and a renamed key strands learner history; confirm this is intended:" "$removed"
    fi
    ;;
esac
exit 0
