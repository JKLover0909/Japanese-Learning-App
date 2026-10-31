# Japanese Learning App

A small, self-hostable Japanese kana practice app. Learners open the link and practise straight away, with no account. They work through six lessons and answer in romaji. The FastAPI backend checks answers and stores each browser's progress in SQLite; the React frontend works on desktop and mobile browsers. A separate, password-protected admin page shows aggregate usage statistics.

## Features

- Six lessons: basic hiragana; extended hiragana; basic katakana; extended katakana; common greetings; and numbers 1–100.
- Practice rounds contain 20 questions by default, with up to five focus questions selected from frequently missed items. Misses increase an item's weakness score by two; each later correct answer reduces it by one.
- A correct answer shows "Chính xác!" for about 0.7 seconds, then the next question opens automatically (Enter skips the wait). A wrong answer or "Không biết" (I don't know) keeps the expected reading on screen until the learner presses "Câu tiếp theo" (Next question) or Enter.
- Server-side answer checking accepts common spelling variants, including `shi`/`si`, `tsu`/`tu`, `chi`/`ti`, `ja`/`zya`, long-vowel spellings such as `gakkou`/`gakkoo`, and macrons such as `kōhī`.
- No learner login: an HttpOnly cookie gives each browser its own anonymous progress. Progress does not follow a learner to another browser or device, and clearing cookies starts over.
- Admin statistics at `/admin` (separate login): anonymous browsers, recent activity, questions and answers, and visits per day. Only aggregate counts are shown; no IP addresses or answers are stored for statistics.
- End-of-chapter listening test: lessons 1–5 form chapter 1, and its test copies the paper "listen and circle" test with 30 questions. The learner hears a kana or word and picks it from four written options a–d. Each attempt draws new questions, distractors, and answer positions. Choices can be changed until "Nộp bài" (Submit), after which the score, per-part results, and the correct options are shown.
- SQLite persistence and Alembic migrations, applied automatically on startup.

## Prerequisites

- Python 3.11 or newer.
- Node.js 20 or newer and npm.
- Docker and Docker Compose (optional, for container deployment).

## Quick start

```bash
./scripts/setup.sh
./scripts/dev.sh
```

Open <http://127.0.0.1:5173>. Vite serves the frontend and proxies API requests to FastAPI at <http://127.0.0.1:8010>. The backend automatically applies migrations and synchronizes validated lesson content on startup. Stop both development servers with Ctrl-C.

For a production-style local server that builds the frontend and serves it from FastAPI:

```bash
./scripts/serve.sh
```

The app is available at <http://127.0.0.1:8010>. To open the production server from a phone on the same Wi-Fi/LAN, use `HOST=0.0.0.0 ./scripts/serve.sh`, then visit `http://<computer-lan-ip>:8010` from the phone. Use this only on a trusted network; LAN HTTP is not encrypted.

## Temporary phone access over the internet

To test from a phone on a different network, keep `./scripts/serve.sh` running and start a tunnel in another terminal:

```bash
./scripts/tunnel.sh ngrok
# or
./scripts/tunnel.sh cloudflare
```

ngrok requires installation and a configured account authtoken (`ngrok config add-authtoken <token>`). Cloudflare quick tunnels require `cloudflared` installed locally. Both produce temporary public URLs that change when the tunnel restarts.

**Security:** A tunnel makes the whole app reachable from the public internet. Anyone with the link can practise anonymously; only `/admin` is protected, by the admin password. Set it up before sharing the link (see [Admin statistics](#admin-statistics)), never commit `.env`, and remember that public tunnel URLs are not a substitute for production hosting.

## Docker

Build and run the app on localhost at port 8010, with persistent database files under `./data`:

```bash
docker compose up --build -d
curl -fsS http://127.0.0.1:8010/api/health
```

Optional Cloudflare quick tunnel:

```bash
docker compose --profile tunnel up --build
```

The app port is intentionally bound to `127.0.0.1`; the tunnel container accesses it over the Compose network. To stop the stack, run `docker compose down`. For configuration, copy `.env.example` to `.env` and edit the settings before starting the containers. Compose pins the database, lesson content, and built frontend paths to the container filesystem; the Docker image uses SQLite at `sqlite:////data/app.db` and serves the built frontend from `/app/frontend/dist`.

## Configuration

All app settings use the `JP_` prefix. Copy `.env.example` to `.env` for local or Compose configuration. The main options are:

| Variable | Default | Description |
|---|---|---|
| `JP_DATABASE_URL` | Repository `data/app.db` SQLite file | SQLAlchemy database URL. |
| `JP_ADMIN_USERNAME` | Empty | Admin statistics username. Admin login is disabled while empty. |
| `JP_ADMIN_PASSWORD_HASH` | Empty | Argon2 hash written by `set_admin_password.py`. Never the password itself. |
| `JP_COOKIE_SECURE` | `auto` | `auto` follows the request scheme; alternatively `true` or `false`. |
| `JP_CONTENT_DIR` | `backend/app/content/lessons` | Source JSON lesson directory. |
| `JP_FRONTEND_DIST` | `frontend/dist` | Built SPA directory served by FastAPI. |
| `JP_AUTO_MIGRATE` | `true` | Apply Alembic migrations at startup. |
| `JP_SESSION_SIZE` | `20` | Questions per practice round. |
| `JP_FOCUS_SIZE` | `5` | Maximum weak-item focus questions per round. |

See [`.env.example`](.env.example) and [Architecture](docs/architecture.md) for details.

## Admin statistics

The admin page is at `/admin` (for example <http://127.0.0.1:8010/admin>). Set its login once from the repository root, in an interactive terminal:

```bash
backend/.venv/bin/python backend/scripts/set_admin_password.py
```

The script asks for the password twice with hidden input and stores only `JP_ADMIN_USERNAME=admin` and the Argon2 hash in the untracked `.env` (mode 600). It never takes the password as an argument or prints it. Restart `./scripts/serve.sh` or the Compose stack afterwards. See [Operations](docs/operations.md#admin-statistics-login) for password changes, rate limiting, and data retention.

## Project layout

```text
backend/       FastAPI API, database models/migrations, lesson content, and backend tests
frontend/      React + TypeScript SPA, served by Vite in development
scripts/       Setup, development, production-style serving, tunnels, and database backup
               (admin password setup lives in backend/scripts/)
Dockerfile     Multi-stage frontend build and non-root backend runtime
docker-compose.yml
.env.example   Documented local/Compose environment settings
docs/          Architecture, API contract, development, and operations guides
research/      Product/design research notes
```

## Tests and validation

```bash
(cd backend && .venv/bin/python -m pytest)
(cd backend && .venv/bin/python -m ruff check .)
(cd backend && .venv/bin/python scripts/validate_content.py)
(cd frontend && npm test)
(cd frontend && npm run typecheck)
(cd frontend && npm run lint)
(cd frontend && npm run build)
```

See [Development](docs/development.md) for content editing and Alembic migration workflow.

## Status and license

**Status: MVP.** This is an early self-hosted learning app. Learner login is temporarily disabled so the app can be shared publicly; progress is per browser. Verify backups and deployment settings before relying on it for long-term data storage. Browser and mobile testing is ongoing.

No license has been chosen yet. Do not assume permission to redistribute or reuse this project.

Listening test audio was generated with VOICEVOX (**VOICEVOX:四国めたん**) and is used under the [voice terms](https://zunko.jp/con_ongen_kiyaku.html); keep that credit with the clips. See [Development](docs/development.md#listening-test-audio) for re-recording.
