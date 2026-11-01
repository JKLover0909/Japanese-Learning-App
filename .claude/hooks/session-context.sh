#!/usr/bin/env bash
# SessionStart: hand a new, resumed or compacted session the latest progress.md entry and the
# features still in progress. Stdout becomes session context.
set -uo pipefail

ROOT=${CLAUDE_PROJECT_DIR:-$PWD}
if [[ -f "$ROOT/progress.md" ]]; then
  echo '# Latest handoff (progress.md)'
  # The file header plus the newest dated entry.
  awk '/^## 20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]/ { n++ } n < 2' "$ROOT/progress.md" | head -n 80
fi
if [[ -f "$ROOT/feature_list.json" ]] && command -v jq >/dev/null; then
  echo
  echo '# Features in progress (feature_list.json)'
  jq -r '.features[] | select(.status == "in_progress") | "- \(.id): \(.title)"' "$ROOT/feature_list.json"
fi
exit 0
