from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.content.schema import LessonFile
from app.main import create_app
from app.models import AuthSession, User

HEADERS = {"X-Requested-With": "jp-practice"}
EMAIL = "Learner@Example.com"
PASSWORD = "correct horse battery"


def _lesson() -> LessonFile:
    items = [
        {"key": f"item-{i}", "prompt": kana, "readings": [kana], "kind": "char", "meaning": None}
        for i, kana in enumerate("あいうえおかきくけこさしすせそたちつてとなにぬねの")
    ]
    return LessonFile(
        slug="hiragana", position=1, title="Hiragana", description="Test lesson", items=items
    )


def _make_client(tmp_path: Path, **overrides: object):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'auth.db'}",
        content_dir=tmp_path / "empty-lessons",
        frontend_dist=tmp_path / "frontend",
        **overrides,
    )
    return TestClient(create_app(settings, lessons=[_lesson()]))


@pytest.fixture
def client(tmp_path: Path):
    with _make_client(tmp_path) as test_client:
        yield test_client


def _register(client: TestClient, email: str = EMAIL, **extra: object):
    return client.post(
        "/api/auth/register",
        headers=HEADERS,
        json={"email": email, "password": PASSWORD, **extra},
    )


def _login(client: TestClient, email: str = EMAIL, password: str = PASSWORD):
    return client.post(
        "/api/auth/login", headers=HEADERS, json={"email": email, "password": password}
    )


def _answer_one(client: TestClient) -> str:
    session = client.post("/api/sessions", headers=HEADERS, json={"lesson_slug": "hiragana"}).json()
    question = session["questions"][0]
    client.post(
        f"/api/sessions/{session['id']}/answers",
        headers=HEADERS,
        json={"position": question["position"], "answer": "?"},
    )
    return session["id"]


def _total_answers(client: TestClient) -> int:
    return client.get("/api/lessons").json()["lessons"][0]["progress"]["total_answers"]


def test_me_is_null_and_creates_no_identity_when_signed_out(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.json() == {"user": None}
    assert "set-cookie" not in response.headers


def test_register_normalises_email_and_signs_in(client: TestClient) -> None:
    response = _register(client)
    assert response.status_code == 201
    user = response.json()["user"]
    assert user["email"] == "learner@example.com"
    assert user["display_name"] == "learner"
    assert "password" not in str(response.json()).lower()
    cookie = response.headers["set-cookie"].lower()
    assert "jp_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/api/auth/me").json()["user"]["email"] == "learner@example.com"


def test_register_requires_csrf_header(client: TestClient) -> None:
    response = client.post("/api/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": PASSWORD},
        {"email": "a@b", "password": PASSWORD},
        {"email": EMAIL, "password": "short"},
        {"email": EMAIL, "password": "x" * 129},
        {"email": EMAIL, "password": PASSWORD, "display_name": "   "},
    ],
)
def test_register_rejects_invalid_input(client: TestClient, payload: dict[str, str]) -> None:
    assert client.post("/api/auth/register", headers=HEADERS, json=payload).status_code == 422


def test_duplicate_email_is_rejected_case_insensitively(client: TestClient) -> None:
    assert _register(client).status_code == 201
    with TestClient(client.app) as other:
        response = _register(other, email="LEARNER@example.COM")
        assert response.status_code == 409
        assert "set-cookie" not in response.headers


def test_registration_keeps_the_browsers_progress(client: TestClient) -> None:
    client.post("/api/learner/init", headers=HEADERS)
    session_id = _answer_one(client)
    assert _total_answers(client) == 1
    assert _register(client).status_code == 201
    assert _total_answers(client) == 1
    assert client.get(f"/api/sessions/{session_id}").status_code == 200


def test_registration_revokes_the_anonymous_cookie(client: TestClient) -> None:
    client.post("/api/learner/init", headers=HEADERS)
    anonymous_cookie = client.cookies.get("jp_learner")
    assert anonymous_cookie
    session_id = _answer_one(client)
    assert _register(client).status_code == 201
    assert client.cookies.get("jp_learner") is None

    # A browser that kept the old cookie must not reach the account without the password.
    client.post("/api/auth/logout", headers=HEADERS)
    stale = TestClient(client.app)
    stale.cookies.set("jp_learner", anonymous_cookie)
    assert stale.get(f"/api/sessions/{session_id}").status_code == 404
    assert stale.get("/api/auth/me").json() == {"user": None}


def test_login_logout_roundtrip(client: TestClient) -> None:
    _register(client)
    assert client.post("/api/auth/logout", headers=HEADERS).status_code == 204
    assert client.get("/api/auth/me").json() == {"user": None}

    response = _login(client, email="learner@example.com")
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "learner@example.com"
    assert client.get("/api/auth/me").json()["user"] is not None


def test_login_from_another_browser_sees_account_progress(client: TestClient) -> None:
    client.post("/api/learner/init", headers=HEADERS)
    _answer_one(client)
    _register(client)
    with TestClient(client.app) as other:
        assert _login(other).status_code == 200
        assert _total_answers(other) == 1


def test_login_does_not_merge_anonymous_progress(client: TestClient) -> None:
    _register(client)
    with TestClient(client.app) as other:
        other.post("/api/learner/init", headers=HEADERS)
        _answer_one(other)
        assert _total_answers(other) == 1
        assert _login(other).status_code == 200
        assert _total_answers(other) == 0


def test_wrong_password_and_unknown_email_look_the_same(client: TestClient) -> None:
    _register(client)
    wrong = _login(client, password="not the password")
    unknown = _login(client, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_login_is_rate_limited(client: TestClient) -> None:
    _register(client)
    codes = [_login(client, password="bad password").status_code for _ in range(6)]
    assert codes[:4] == [401] * 4
    assert codes[4] == 429
    assert _login(client).status_code == 429


def test_registration_is_rate_limited(client: TestClient) -> None:
    codes = [
        _register(client, email=f"user{i}@example.com").status_code for i in range(12)
    ]
    assert codes[:10] == [201] * 10
    assert codes[10:] == [429, 429]


def test_logout_deletes_the_server_side_session(client: TestClient) -> None:
    _register(client)
    token = client.cookies.get("jp_session")
    assert token
    client.post("/api/auth/logout", headers=HEADERS)
    stale = TestClient(client.app)
    stale.cookies.set("jp_session", token)
    assert stale.get("/api/auth/me").json() == {"user": None}
    with client.app.state.session_factory() as db:
        assert db.query(AuthSession).count() == 0


def test_expired_session_is_ignored(client: TestClient) -> None:
    _register(client)
    with client.app.state.session_factory() as db:
        from datetime import UTC, datetime, timedelta

        for row in db.query(AuthSession):
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/auth/me").json() == {"user": None}


def test_forged_session_cookie_falls_back_to_anonymous(client: TestClient) -> None:
    client.cookies.set("jp_session", "forged-token")
    assert client.get("/api/auth/me").json() == {"user": None}
    response = client.post("/api/learner/init", headers=HEADERS)
    assert response.status_code == 200
    assert response.cookies.get("jp_learner")


def test_password_is_stored_as_an_argon2_hash(client: TestClient) -> None:
    _register(client)
    with client.app.state.session_factory() as db:
        user = db.query(User).filter_by(email="learner@example.com").one()
        assert user.password_hash.startswith("$argon2id$")
        assert PASSWORD not in user.password_hash
        assert user.username.startswith("u-")


def test_registration_code_is_enforced(tmp_path: Path) -> None:
    with _make_client(tmp_path, registration_code="open-sesame") as client:
        assert client.get("/api/config").json()["registration_code_required"] is True
        assert _register(client).status_code == 403
        assert _register(client, registration_code="wrong").status_code == 403
        assert _register(client, registration_code="open-sesame").status_code == 201


def test_config_reports_open_registration(client: TestClient) -> None:
    body = client.get("/api/config").json()
    assert body["registration_open"] is True
    assert body["registration_code_required"] is False


def test_admin_stays_independent_of_learner_login(client: TestClient) -> None:
    _register(client)
    assert client.get("/api/admin/overview").status_code == 401
