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

## 2026-11-21 — Learner accounts (email + password), uncommitted
- Done: optional accounts. Backend: migration `0007_user_accounts` (`users.email`, unique),
  `/api/auth/register|login|logout|me`, `deps.get_current_user` (login session first, then the
  anonymous cookie), rate limits, `JP_ALLOW_REGISTRATION` / `JP_REGISTRATION_CODE`. Frontend:
  `/login`, `/register`, `AuthContext`, account menu in the header. Updated `docs/api.md`,
  `docs/architecture.md`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `.env.example`.
  Design: registering converts the browser's anonymous user in place (progress kept) and revokes
  the `jp_learner` cookie; logging in does not merge anonymous progress.
- In progress (files touched, uncommitted?): all of the above is uncommitted and not pushed.
  `.env.example` could not be edited (permission rule denies it): add the three `JP_` settings
  by hand (documented in README). The running server on :8010 still runs the old code.
- Validation: scripts/check.sh --build → pass (pytest, vitest 42, tsc, eslint, build). Migration
  0007 checked upgrade → downgrade → upgrade on a throwaway SQLite DB with existing rows.
- Blockers / decisions needed: Google sign-in needs a user-created OAuth client and an https
  URL. Restart the app to load the new code (migration runs on startup against the real DB:
  back it up first). `noto-sans-cjk.ttc` is kept, untracked.
- Next: commit and push when the user agrees; restart; then `google-sign-in` if wanted.

## 2026-11-21 — Commit the in-progress work (before starting user accounts)
- Done: committed the frontend build configs (`track-build-configs`) and the three in-progress
  features as separate commits: dark theme styles, theme mode, kana table, chapter-test sample
  question (backend, API docs and UI) and the practice prompt wording. Rebased onto `origin/main`
  (`7990bea`) without conflicts. Marked those four features `implemented`.
- In progress (files touched, uncommitted?): only the untracked, unused
  `frontend/public/assets/noto-sans-cjk.ttc` (18.6 MB) remains; deliberately not committed.
  Not pushed yet.
- Validation: scripts/check.sh --build → pass after the rebase.
- Blockers / decisions needed: keep or delete `noto-sans-cjk.ttc`. Google OAuth needs a client
  id/secret created by the user and an ngrok/Cloudflare HTTPS URL (Google rejects LAN and
  Tailscale IPs).
- Next: user accounts (email + password, Google sign-in) per the approved plan in
  `~/.claude/plans/declarative-swimming-gizmo.md`: migration `0007_user_accounts`, `/api/auth/*`,
  login and register pages.

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
