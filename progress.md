# Progress log

Session handoffs, newest first. At the end of every session add an entry at the top of the log using
the template; keep older entries unchanged. Feature status lives in `feature_list.json`.

Template:

```
## YYYY-MM-DD — <goal in a few words>
- Done:
- In progress (files touched, uncommitted?):
- Validation: scripts/check.sh → <pass, or which gates failed>
- Blockers / decisions needed:
- Next:
```

## 2026-11-03 — MIT licence
- Done: added `LICENSE` (MIT, chosen by the user); updated the README licence section, the
  `CLAUDE.md` git rule and the `license` entry in `feature_list.json`. No application code changed.
- In progress (files touched, uncommitted?): none from this session. The uncommitted work listed
  on 2026-11-01 is in the local clone, not in this commit.
- Validation: documentation-only change; `feature_list.json` parses and `git diff --check` is clean.
- Blockers / decisions needed: whether to keep the unused 18.6 MB `noto-sans-cjk.ttc`.
- Next: commit the frontend build configs (`track-build-configs`) so clean clones and Docker build;
  then finish and commit the three in-progress features.

## 2026-11-01 — Harness setup (CLAUDE.md, feature list, progress log, hooks)
- Done: added `CLAUDE.md`, `feature_list.json`, `progress.md`, `scripts/check.sh`,
  `.claude/settings.json` and `.claude/hooks/`. No application code changed.
- In progress (not from this session, uncommitted): chapter-test sample question, theme mode,
  lesson kana table: 15 modified + 9 untracked files under `backend/` and `frontend/`
  (see `git status`). Do not revert them.
- Validation (working tree, including the uncommitted work): pytest 45 passed, ruff clean,
  validate_content OK, audio 743/743, vitest 33 passed, tsc -b clean, eslint clean. A clean
  checkout of this commit cannot run the frontend checks until `track-build-configs` is done.
  Hooks verified live in-session: `git add -A` and reading `.env` were blocked.
- Blockers / decisions needed: licence choice; whether to keep the unused 18.6 MB
  `noto-sans-cjk.ttc`.
- Next: commit the frontend build configs (`track-build-configs`) so clean clones and Docker build;
  then finish and commit the three in-progress features.
