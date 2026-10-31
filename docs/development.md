# Development

## Prerequisites and setup

Use Python 3.11 or newer and Node.js 20 or newer. From the repository root:

```bash
./scripts/setup.sh
```

This creates `backend/.venv`, installs the backend and development dependencies, and installs frontend dependencies. Start both development servers with:

```bash
./scripts/dev.sh
```

Open <http://127.0.0.1:5173>. Vite proxies `/api` requests to FastAPI on port 8010. The API health endpoint is <http://127.0.0.1:8010/api/health>.

## Tests, lint, and content validation

Run the backend suite from `backend/`:

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python scripts/validate_content.py
```

Run frontend checks from `frontend/`:

```bash
npm test
npm run typecheck
npm run lint
npm run build
```

The content validator checks lesson schemas, character/reading support, lesson-specific rules, key and prompt uniqueness, and required item counts. All lesson JSON is validated on application startup as well; invalid content prevents startup.

## Editing lesson content

The six source-of-truth JSON files are in `backend/app/content/lessons/`. Each item has a stable `key`, prompt, one or more kana `readings`, kind, optional Vietnamese meaning, and tags. The application synchronizes these files to the database by key at startup; removed items are deactivated instead of deleted so existing learner history is retained.

**Never change or reuse an item's key after it has been published.** Progress is associated with the item identity; changing a key creates a new item and strands the old item's history. To correct a prompt, reading, meaning, or tags, keep its key unchanged. If an item should no longer be served, remove it from JSON; synchronization marks it inactive. Treat lesson slugs and their meanings as stable too, since sessions and progress refer to them.

Lesson 5 (`greetings`) and lesson 6 (`numbers`) were split from the former `greetings-numbers` lesson. Content sync moves those legacy item rows to the new lessons by key; keep the `p-…` and `n-…` keys unchanged so this migration and existing progress keep working. The `numbers` lesson must contain exactly the prompts 1–100.

After editing content, run `python scripts/validate_content.py` from `backend/` and review the resulting diff before starting the application.

## Listening test audio

The chapter test plays clips recorded with [VOICEVOX](https://voicevox.hiroshiba.jp/) (voice
四国めたん). The clips and `backend/app/content/audio.json` are committed, so normal
development does not need VOICEVOX. After adding or changing word or kana items in lessons
1–5, record the new prompts from `backend/`:

```bash
docker run --rm -d --name jp-voicevox -p 127.0.0.1:50021:50021 \
    voicevox/voicevox_engine:cpu-ubuntu22.04-0.25.2
.venv/bin/python scripts/generate_audio.py     # records only prompts without a clip
docker stop jp-voicevox
.venv/bin/python scripts/generate_audio.py --check
```

The script compares each clip with the reading VOICEVOX reports. If they differ (for
example は read as the particle "wa"), it re-records in kana mode, and fails if the reading
is still wrong. `--check` needs no engine. It confirms every test prompt has a manifest entry
and an existing file; `tests/test_chapter_test.py` checks the same. Keep the credit
「VOICEVOX:四国めたん」 visible wherever the clips are used, per the
[voice terms](https://zunko.jp/con_ongen_kiyaku.html).

## Database schema and migrations

Alembic migrations live under `backend/alembic/`. The application applies `alembic upgrade head` on startup when `JP_AUTO_MIGRATE=true` (the default). For a schema change:

1. Update the SQLAlchemy models and related API/services/tests.
2. From `backend/`, generate a migration with `.venv/bin/alembic revision --autogenerate -m "describe change"`.
3. Review and edit the generated migration. SQLite changes use Alembic batch operations; never assume autogeneration is complete or correct.
4. Test against a disposable database and run the complete backend suite.
5. Back up the production database before deploying the application version that includes the migration.

Do not edit an already-applied migration. Add a new revision instead. Schema migrations and lesson JSON sync are separate: migrations alter the database schema; content sync updates lesson and item records.

## Local admin login

Learner pages need no login. To try the admin page (`/admin`) locally, run
`backend/.venv/bin/python backend/scripts/set_admin_password.py` from the repository root
and restart `scripts/dev.sh` or `scripts/serve.sh`; both load the repository-root `.env`
when it exists. Tests use their own throwaway admin hash and never read `.env`.

## Configuration and pull requests

Application environment variables use the `JP_` prefix; see [`.env.example`](../.env.example) and the configuration table in [Architecture](architecture.md). Keep credentials, database files, and local environment files out of version control. Update [the API contract](api.md) before changing API behavior, and update the documentation when setup, operational behavior, or content rules change.
