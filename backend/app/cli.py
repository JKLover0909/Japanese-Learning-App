"""Administrative commands: ``python -m app.cli create-user/set-password/list-users``."""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.config import get_settings
from app.db import create_db_engine, create_session_factory
from app.models import User
from app.security import hash_password


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-user", help="create a user when public registration is closed")
    create.add_argument("username")
    create.add_argument("--display-name")
    create.add_argument("--password", help="omit to securely prompt")
    set_password = sub.add_parser("set-password", help="change an existing user's password")
    set_password.add_argument("username")
    set_password.add_argument("--password", help="omit to securely prompt")
    sub.add_parser("list-users", help="list usernames and display names")
    return parser


def _password(value: str | None) -> str:
    password = value if value is not None else getpass.getpass("Password: ")
    if not 8 <= len(password) <= 128:
        raise ValueError("Password must be 8..128 characters.")
    return password


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    settings.ensure_data_dir()
    engine = create_db_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with factory() as db:
            if args.command == "list-users":
                users = db.scalars(select(User).order_by(User.username))
                for user in users:
                    print(f"{user.username}\t{user.display_name}")
                return 0
            username = args.username.lower()
            if args.command == "create-user":
                if db.scalar(select(User.id).where(User.username == username)) is not None:
                    print(f"User {username!r} already exists.", file=sys.stderr)
                    return 1
                password = _password(args.password)
                user = User(
                    username=username,
                    password_hash=hash_password(password),
                    display_name=args.display_name or username,
                )
                db.add(user)
                db.commit()
                print(f"Created user {username!r}.")
                return 0
            user = db.scalar(select(User).where(User.username == username))
            if user is None:
                print(f"User {username!r} does not exist.", file=sys.stderr)
                return 1
            user.password_hash = hash_password(_password(args.password))
            db.commit()
            print(f"Updated password for {username!r}.")
            return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
