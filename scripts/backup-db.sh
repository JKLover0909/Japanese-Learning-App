#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT_DIR/backend/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  printf 'Python executable not found: %s. Run scripts/setup.sh first.\n' "$PYTHON" >&2
  exit 1
fi

# Read only JP_DATABASE_URL so the backup utility never sources arbitrary shell code.
FROM_ENV_FILE=false
if [[ -n "${JP_DATABASE_URL:-}" ]]; then
  DATABASE_URL="$JP_DATABASE_URL"
elif [[ -f "$ROOT_DIR/.env" ]]; then
  FROM_ENV_FILE=true
  DATABASE_URL="$("$PYTHON" -I -c 'from pathlib import Path; from dotenv import dotenv_values; print(dotenv_values(Path(__import__("sys").argv[1])).get("JP_DATABASE_URL", ""))' "$ROOT_DIR/.env")"
else
  DATABASE_URL=''
fi
if [[ -z "$DATABASE_URL" ]]; then
  DATABASE_URL="sqlite:///$ROOT_DIR/data/app.db"
fi

exec "$PYTHON" -I - "$ROOT_DIR" "$DATABASE_URL" "$FROM_ENV_FILE" <<'PY'
import datetime as dt
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import unquote

root = Path(sys.argv[1])
url = sys.argv[2]
prefix = "sqlite:///"
if not url.startswith(prefix):
    raise SystemExit("Online backup supports file-based SQLite databases only.")
database = url[len(prefix):].split("?", 1)[0]
if not database or database == ":memory:" or database.startswith("file:"):
    raise SystemExit("Online backup requires a file-based SQLite database.")
if database.startswith("/"):
    source = Path(unquote(database))
else:
    # Settings load a local .env while the server is launched from backend/.
    # Process overrides conventionally resolve relative to the repository root.
    base = root / "backend" if sys.argv[3] == "true" else root
    source = (base / unquote(database)).resolve()
if not source.is_file():
    raise SystemExit(f"Database file does not exist: {source}")

backup_dir = root / "data" / "backups"
backup_dir.mkdir(parents=True, exist_ok=True)
timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
target = backup_dir / f"app-{timestamp}.db"
try:
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as source_db:
        with sqlite3.connect(target) as backup_db:
            source_db.backup(backup_db)
except Exception:
    target.unlink(missing_ok=True)
    raise
os.chmod(target, 0o600)
print(f"Database backup created: {target}")
PY
