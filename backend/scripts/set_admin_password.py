"""Store the admin login as an Argon2 hash in the untracked ``.env`` file.

Usage (from the repository root, in an interactive terminal)::

    backend/.venv/bin/python backend/scripts/set_admin_password.py [--username NAME]

``--env-file PATH`` writes somewhere other than the repository-root ``.env``.

The password is read with a hidden prompt only: it is never accepted as an
argument, never written to disk and never printed. Only ``JP_ADMIN_USERNAME``
and ``JP_ADMIN_PASSWORD_HASH`` are added or replaced; every other line in the
env file is kept. Restart the server afterwards so it loads the new values.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.security import hash_password  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
MAX_PASSWORD = 128  # matches AdminLoginRequest.password in app/api/admin.py
KEYS = ("JP_ADMIN_USERNAME", "JP_ADMIN_PASSWORD_HASH")


def updated_env(text: str, values: dict[str, str]) -> str:
    """Replace or append ``KEY='value'`` lines; single quotes keep ``$`` literal."""
    lines = [
        line
        for line in text.splitlines()
        if not any(line.lstrip().startswith(f"{key}=") for key in values)
    ]
    while lines and not lines[-1].strip():
        lines.pop()
    if lines:
        lines.append("")
    lines.append("# Admin statistics login (written by backend/scripts/set_admin_password.py).")
    lines.extend(f"{key}='{value}'" for key, value in values.items())
    return "\n".join(lines) + "\n"


def write_private(path: Path, content: str) -> None:
    """Atomically replace ``path`` with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".env.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Set the admin statistics login.")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()

    if not USERNAME_PATTERN.fullmatch(args.username):
        print("Username must be 1-64 letters, digits, '.', '_' or '-'.", file=sys.stderr)
        return 2
    if not sys.stdin.isatty():
        print(
            "Run this in an interactive terminal; the password is only read from a hidden prompt.",
            file=sys.stderr,
        )
        return 2

    password = getpass.getpass(f"New password for admin '{args.username}': ")
    if not password or len(password) > MAX_PASSWORD:
        print(f"Password must be 1-{MAX_PASSWORD} characters.", file=sys.stderr)
        return 2
    if getpass.getpass("Repeat the password: ") != password:
        print("Passwords do not match; nothing was changed.", file=sys.stderr)
        return 1
    if len(password) < 12:
        print("Warning: a password of at least 12 characters is recommended.", file=sys.stderr)

    env_file = args.env_file.resolve()
    current = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    write_private(
        env_file,
        updated_env(current, {KEYS[0]: args.username, KEYS[1]: hash_password(password)}),
    )
    del password
    print(f"Saved admin login for '{args.username}' to {env_file} (mode 600).")
    print("Restart the server (scripts/serve.sh) to apply it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
