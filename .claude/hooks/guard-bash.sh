#!/usr/bin/env bash
# PreToolUse guard for Bash. Denies commands that would expose secrets, destroy local data or
# uncommitted work, or rewrite shared history; asks before commits, pushes and dependency changes.
# Prints a permission decision as JSON; no output means "no opinion".
set -euo pipefail

cmd=$(jq -r '.tool_input.command // empty')
[[ -n "$cmd" ]] || exit 0

decide() {
  jq -n --arg decision "$1" --arg reason "$2" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: $decision, permissionDecisionReason: $reason}}'
  exit 0
}
matches() { grep -Eq -- "$1" <<<"$cmd"; }

# A git invocation (allowing -C <dir> / -c <key=value> before the subcommand), and the
# arguments that follow it up to the end of that command.
git_='(^|[^[:alnum:]_./-])git([[:space:]]+-[Cc][[:space:]]+[^[:space:]]+)*[[:space:]]+'
args_='([^;&|]*[[:space:]])?'
# The local SQLite database and anything under data/.
data_='(^|[[:space:]/"'\''=])data/|\.(db|sqlite3)(-wal|-shm|-journal)?([^[:alnum:]_]|$)'

# --- deny ------------------------------------------------------------------------------------
if grep -Eq '(^|[[:space:]/"'\''=<>(:])\.env(\.[[:alnum:]_-]+)?([[:space:]"'\'';|&)<>]|$)' <<<"${cmd//.env.example/}"; then
  decide deny 'Commands must not touch .env files (secrets). .env.example documents the settings; ask the user if a real value is needed.'
fi
if matches '(^|[^[:alnum:]_-])rm[[:space:]]' && { matches "$data_" || matches 'assets/audio'; }; then
  decide deny 'Do not delete the local database (data/, *.db: it may hold real learner data) or the recorded VOICEVOX clips. Ask the user.'
fi
if matches "${git_}push${args_}(--force|--force-with-lease|-[[:alpha:]]*f[[:alpha:]]*|\+[^[:space:]]+)([[:space:]=]|$)"; then
  decide deny 'Force pushes are not allowed.'
fi
if matches "${git_}reset${args_}--hard" || matches "${git_}clean${args_}(-[[:alpha:]]*f|--force)" \
  || matches "${git_}checkout${args_}(--|\.)([[:space:]]|$)"; then
  decide deny 'This discards uncommitted changes, which may belong to the user or another session. Ask the user.'
fi
if restore=$(grep -Eo "${git_}restore[^;&|]*" <<<"$cmd") \
  && { ! grep -Eq '[[:space:]](--staged|-S)([[:space:]]|$)' <<<"$restore" \
    || grep -Eq '[[:space:]](--worktree|-W)([[:space:]]|$)' <<<"$restore"; }; then
  decide deny 'git restore without --staged discards working-tree changes, which may not be yours. Ask the user.'
fi
if matches "${git_}add${args_}(-A|--all|\.|-u|--update|:/|\*)([[:space:]]|$)" \
  || matches "${git_}commit${args_}(--all|-[[:alpha:]]*a[[:alpha:]]*)([[:space:]]|$)"; then
  decide deny 'Stage explicit paths only: the working tree holds uncommitted work that is not part of this change.'
fi
if matches '(^|[^[:alnum:]_./-])npx[[:space:]]'; then
  decide deny 'Do not use npx here: it has resolved unrelated packages (tsc@2, vitest 5, eslint 10). Use frontend/node_modules/.bin/<tool> or npm run <script> from frontend/.'
fi

# --- ask -------------------------------------------------------------------------------------
if matches "$data_"; then
  decide ask 'This command touches data/ or a database file, which may hold real learner data.'
fi
if matches "${git_}(commit|push)([[:space:]]|$)"; then
  decide ask 'Commit or push only when the user asked for it.'
fi
if matches "${git_}stash([[:space:]]+(push|save|pop|apply|drop|clear|-)|[[:space:]]*$)"; then
  decide ask 'git stash hides or rewrites uncommitted work that may not be yours.'
fi
if matches 'alembic[^;&|]*[[:space:]]downgrade'; then
  decide ask 'An Alembic downgrade can drop columns or tables in the local database.'
fi
if matches '(^|[^[:alnum:]_-])npm[[:space:]]+(install|i|add|uninstall|remove|rm|update)[[:space:]]+[^-[:space:]]' \
  || matches '(^|[^[:alnum:]_-])pip3?[[:space:]]+(install|uninstall)'; then
  decide ask 'This changes project dependencies.'
fi
exit 0
