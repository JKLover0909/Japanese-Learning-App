import importlib.util
import stat
from pathlib import Path

from dotenv import dotenv_values

from app.security import hash_password, verify_password

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "set_admin_password.py"
_spec = importlib.util.spec_from_file_location("set_admin_password", SCRIPT)
assert _spec and _spec.loader
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def test_env_update_keeps_other_settings_and_round_trips_the_hash(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "JP_COOKIE_SECURE=auto\nJP_ADMIN_USERNAME='old'\nJP_ADMIN_PASSWORD_HASH='old-hash'\n",
        encoding="utf-8",
    )
    password_hash = hash_password("test-only-password")
    assert "$" in password_hash

    script.write_private(
        env_file,
        script.updated_env(
            env_file.read_text(encoding="utf-8"),
            {"JP_ADMIN_USERNAME": "admin", "JP_ADMIN_PASSWORD_HASH": password_hash},
        ),
    )

    # uvicorn --env-file parses with python-dotenv; single quotes keep "$" literal.
    values = dotenv_values(env_file)
    assert values == {
        "JP_COOKIE_SECURE": "auto",
        "JP_ADMIN_USERNAME": "admin",
        "JP_ADMIN_PASSWORD_HASH": password_hash,
    }
    assert verify_password(values["JP_ADMIN_PASSWORD_HASH"] or "", "test-only-password")
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    assert env_file.read_text(encoding="utf-8").count("JP_ADMIN_USERNAME=") == 1
    assert list(tmp_path.iterdir()) == [env_file]
