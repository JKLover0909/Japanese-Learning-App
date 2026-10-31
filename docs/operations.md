# Operations

## Run the application

For local development, install dependencies and start the backend and Vite together:

```bash
./scripts/setup.sh
./scripts/dev.sh
```

For a production-style local run, build the SPA and serve it with FastAPI:

```bash
./scripts/serve.sh
```

The default bind address is `127.0.0.1:8010`. The built frontend is served by the backend from `frontend/dist`; `/api/health` is the health endpoint. To access the production server from another device on the same LAN, bind to all interfaces:

```bash
HOST=0.0.0.0 ./scripts/serve.sh
```

Only use `0.0.0.0` on a trusted network and allow the port through the machine firewall only as needed. A LAN connection is not encrypted; do not use it over an untrusted network.

## Admin statistics login

Learners do not sign in. The only login is the admin statistics page at `/admin`, which shows
aggregate usage (anonymous browsers, recent activity, questions and answers, visits per day).
Set it up once from the repository root, in an interactive terminal:

```bash
backend/.venv/bin/python backend/scripts/set_admin_password.py            # username "admin"
backend/.venv/bin/python backend/scripts/set_admin_password.py --username someone
```

The script prompts twice for the password with hidden input, then writes only
`JP_ADMIN_USERNAME` and the Argon2 hash `JP_ADMIN_PASSWORD_HASH` into the untracked `.env`
(mode 600), keeping other lines. It never accepts the password as an argument or prints it or
the hash. Restart `./scripts/serve.sh` (or `docker compose up -d`) to load the new values. To
change the password, run it again and restart; existing admin sessions expire within 12 hours;
delete the rows in the `admin_sessions` table to end them immediately.

While either variable is empty, `/api/admin/login` returns `503` and the overview stays
locked. Do not put the password itself in `.env`, shell commands, compose files or the
frontend. After 5 wrong attempts from one address within 5 minutes, admin login is refused
for 5 minutes (in memory; a restart clears it).

## Temporary public tunnel

Start `./scripts/serve.sh` in one terminal, then in another run one of:

```bash
./scripts/tunnel.sh ngrok
./scripts/tunnel.sh cloudflare
```

The ngrok option uses `/snap/bin/ngrok` when available, otherwise `ngrok` on `PATH`; it requires an account authtoken configured with `ngrok config add-authtoken <token>`. The Cloudflare option starts a temporary quick tunnel when `cloudflared` is installed. The URL changes when the tunnel stops. Keep the local server running for the duration of access. `tunnel.sh` prints a note (without any values) when the admin login is not configured.

The public URL exposes the full app and its API. Anyone with the link can practise without an account; each browser gets its own anonymous progress, which is lost if its cookies are cleared. The admin page is protected only by the admin password, so use a long unique one. Do not use a quick tunnel as a production hosting service.

With Docker Compose, the app is bound to `127.0.0.1:8010` on the host. Start a Cloudflare quick tunnel in a separate container with:

```bash
docker compose --profile tunnel up --build
```

The tunnel container waits for the app health check. To run only the app, use `docker compose up --build -d`. The optional `.env` file is loaded by Compose when present. To stop the services, run `docker compose down`.

## Database backup and restore

The default database is `data/app.db`. Back up a running SQLite database using SQLite's online backup API (safe with WAL mode):

```bash
./scripts/backup-db.sh
```

The script creates a timestamped, owner-readable backup under `data/backups/`. Backups contain anonymous learner progress, visit timestamps, and hashed cookie tokens (plus any legacy account password hashes); keep them private and copy them to a secure, separate storage location. The `data/` directory is intentionally excluded from version control. Ensure there is sufficient disk space and periodically test restoring a backup.

For restore, first stop the app (and any other process using the database), then preserve the current files and restore the selected backup as the database file:

```bash
docker compose down                 # if using Compose
cp data/app.db "data/app.db.before-restore-$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
cp data/backups/app-YYYYmmdd-HHMMSS.db data/app.db
```

For a non-Docker install, stop the server before the same copy operation. Keep the restored `app.db` owned and readable/writable by the account running the app. Start the app again; its normal startup migration will bring the restored schema to the current revision. Do not restore an untrusted database file.

For a database URL other than the default file-based SQLite URL, set `JP_DATABASE_URL` in the environment. The backup helper intentionally supports only local SQLite files; use the database provider's native backup procedure for any other database type.

## Upgrades

1. Read the release notes and check for schema/content changes.
2. Back up `data/app.db` before replacing code or starting a version with new migrations.
3. Update the checkout, then rebuild/recreate the app (`docker compose up --build -d`) or install updated backend/frontend dependencies and run `./scripts/serve.sh`.
4. Check `docker compose ps` or the server logs, then verify `curl -fsS http://127.0.0.1:8010/api/health`.
5. Keep a restorable backup until the app and learner data have been verified.

Startup runs migrations automatically by default. To disable automatic migration for a controlled deployment, set `JP_AUTO_MIGRATE=false` and run the reviewed Alembic upgrade separately from `backend/` with the same `JP_DATABASE_URL` configured.

## Usage data and retention

The admin overview counts anonymous browser identities, not people: one person on two
browsers counts twice, and clearing cookies creates a new identity. Visit events (identity ID
and a minute-precision UTC time; no IP address or user agent) are deleted after 90 days when
the overview is opened. Anonymous identities and their progress remain until removed from the
database.

## Legacy user administration CLI

Learner accounts are disabled, so these commands are only for inspecting or maintaining
account rows created before anonymous mode; they do not enable learner login or the admin page.
Run commands from `backend/` using the configured virtual environment and the same environment variables/database URL as the server:

```bash
cd backend
.venv/bin/python -m app.cli create-user
.venv/bin/python -m app.cli set-password <username>
.venv/bin/python -m app.cli list-users
```

`list-users` also lists the internal `anon-…` rows of anonymous browsers. The CLI prompts for passwords rather than accepting them as command-line arguments. Creating a user stores an Argon2 password hash; listing users does not reveal hashes. Run administrative commands locally with an account that can access the production database, and protect terminal history and backups. If the CLI command or an option differs in a specific release, check `.venv/bin/python -m app.cli --help` for the installed version.
