# CLAUDE.md — Japanese Learning App

Self-hosted app for Vietnamese learners practising kana, greetings and numbers by typing romaji, plus a
chapter 1 listening test. One FastAPI process serves `/api` and the built React SPA. Learners are
anonymous (cookie `jp_learner`); only the admin statistics page has a login.

Read these before changing the matching area; they are the source of truth and this file does not
repeat them:

- [docs/architecture.md](docs/architecture.md): layout, data model, learning rules, chapter test, security, `JP_` settings
- [docs/api.md](docs/api.md): the HTTP contract
- [docs/development.md](docs/development.md): setup, lesson content, audio, migrations
- [docs/operations.md](docs/operations.md): deployment, backups, tunnel

## Session protocol

1. **Start:** the SessionStart hook prints the latest `progress.md` entry and in-progress features.
   Run `git status --short` and treat every modified or untracked file you did not create in this
   session as someone else's work in progress.
2. **Work:** pick one feature from `feature_list.json` (or the user's request). Keep each change small
   enough to validate in the same session.
3. **End:** run `scripts/check.sh`, then add a dated entry at the top of the log in `progress.md` and
   update the feature's `status`/`notes` in `feature_list.json`. Never mark a feature `implemented`
   while a check fails.

## Validation

```bash
scripts/check.sh            # everything below; prints FAILED: <names> and exits 1 on any failure
scripts/check.sh backend    # pytest, ruff, validate_content.py, generate_audio.py --check
scripts/check.sh frontend   # vitest, tsc -b, eslint
scripts/check.sh --build    # adds vite build (needed after touching vite/tsconfig/public assets)
```

Single checks, from the package directory:

| What | Command |
|---|---|
| backend tests | `cd backend && .venv/bin/python -m pytest -q` (one file: `... pytest tests/test_chapter_test.py`) |
| backend lint | `cd backend && .venv/bin/python -m ruff check .` |
| lesson content | `cd backend && .venv/bin/python scripts/validate_content.py` |
| audio manifest | `cd backend && .venv/bin/python scripts/generate_audio.py --check` (no VOICEVOX needed) |
| frontend tests | `cd frontend && ./node_modules/.bin/vitest run` (one file: `... vitest run src/pages/PracticePage.test.tsx`) |
| types | `cd frontend && ./node_modules/.bin/tsc -b` |
| frontend lint | `cd frontend && ./node_modules/.bin/eslint .` |

- **Never use `npx`.** It has resolved unrelated packages here (`tsc@2`, vitest 5, eslint 10) and
  produced false failures. Use `frontend/node_modules/.bin/<tool>` or `npm run <script>`.
- Use `backend/.venv/bin/python`, not the system or conda Python.
- Missing `backend/.venv` or `frontend/node_modules`: ask the user before running `scripts/setup.sh`
  (it installs packages).

## Project rules

**Content (`backend/app/content/lessons/*.json`)**
- An item's `key` is permanent. Never rename or reuse one; to fix an item, keep the key and edit its
  prompt, readings, meaning or tags. Deleting an item marks it inactive; it does not remove history.
- Lesson slugs are stable too. Keep the `p-…`/`n-…` keys (legacy split from `greetings-numbers`).
- Limits are enforced by `validate_content.py`, which also runs at startup (invalid content stops the
  app): 150–260 items per kana lesson, ≥ 40 phrases in `greetings`, `numbers` exactly 1..100.
- Adding or changing a word/kana prompt in lessons 1–5 needs a new VOICEVOX clip
  (`generate_audio.py`, see docs). Do not hand-edit `audio.json` or files in `frontend/public/assets/audio/`.
- Keep the credit 「VOICEVOX:四国めたん」 visible wherever clips play (voice licence terms).

**API contract**
- A change to request/response shapes touches three files together: `backend/app/api/schemas.py`,
  `frontend/src/api/types.ts` and `docs/api.md`, plus tests on both sides.
- State-changing requests require the header `X-Requested-With: jp-practice` (`security.py`,
  `client.ts`). Keep it on new POST/PUT/DELETE endpoints and calls.
- Do not loosen the CSP, cookie flags (`HttpOnly`, `SameSite`, admin `Path=/api/admin`) or rate limits
  without the user's explicit request.

**Database**
- Schema changes go in a new Alembic revision (`cd backend && .venv/bin/alembic revision --autogenerate -m "..."`),
  reviewed by hand and using batch operations for SQLite. Never edit a committed migration. Head is
  `0006_chapter_tests`; there is no `0003` (the chain goes `0002 → 0004`), so check `alembic heads`
  rather than counting files.
- Content sync (lesson JSON → rows) is separate from migrations.

**Learning rules**
- Weakness/streak/mastery, session size and focus selection live in `services/progress.py` and
  `services/selection.py` and are documented in architecture.md. Changing a constant changes every
  learner's behaviour: treat it as a product decision, update the docs and tests with it.
- UI timings are deliberate: practice auto-advances 700 ms after a correct answer only; the test
  page advances 450 ms after a first choice (`NEXT_QUESTION_DELAY_MS`).

**Frontend**
- UI copy is Vietnamese; Japanese text carries `lang="ja"`. Keep keyboard flows working (Enter in
  practice; a–d/1–4, R, ←/→ on the test page) and their tests.
- Only `frontend/src/api/client.ts` calls `fetch`; pages use the `api` object.

**Secrets and data**
- Never read, print or commit `.env`, `data/` or `*.db*`. Settings are documented in `.env.example`.
- Never pass a password as a command argument. The admin password is set interactively with
  `backend/.venv/bin/python backend/scripts/set_admin_password.py` (the user runs it).
- Tests create their own throwaway database and admin hash; they must never depend on `.env`.

**Git**
- Commit or push only when the user asks. Stage explicit paths, never `git add -A`/`.`.
- End commit messages with `Co-Authored-By: Claude Code <noreply@anthropic.com>`.
- No licence has been chosen; do not add one unless the user picks it.

## Guardrails (`.claude/`)

`settings.json` registers hooks in `.claude/hooks/`:

- `guard-bash.sh`: blocks `.env` access, deleting `data/`/`*.db`/audio, force-push, `reset --hard`,
  `clean -f`, discarding checkouts/restores, `git add -A`/`commit -a`, and `npx`. It asks before
  commit, push, stash, Alembic downgrade and dependency changes.
- `guard-files.sh`: blocks file tools on `.env*` (except `.env.example`), `data/` and database files,
  and edits to committed migrations. It asks before editing generated audio files.
- `check-edited-file.sh`: after each edit, runs ruff (Python) or eslint (TS); for lesson JSON it runs
  `validate_content.py` and lists any keys removed since `HEAD`. Problems come back as feedback; it
  never rewrites files.
- `session-context.sh`: prints the latest handoff at session start.

If a guard blocks something the user really wants, explain and let the user run it; do not work around
the hook.
