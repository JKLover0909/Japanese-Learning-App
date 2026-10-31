from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.content.schema import LessonFile
from app.main import create_app
from app.security import hash_password

HEADERS = {"X-Requested-With": "jp-practice"}


@pytest.fixture
def client(tmp_path: Path):
    items = [
        {
            "key": f"item-{i}",
            "prompt": kana,
            "readings": [kana],
            "kind": "char",
            "meaning": None,
        }
        for i, kana in enumerate("あいうえおかきくけこさしすせそたちつてとなにぬねの")
    ]
    lesson = LessonFile(
        slug="hiragana",
        position=1,
        title="Hiragana",
        description="Test lesson",
        items=items,
    )
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        content_dir=tmp_path / "empty-lessons",
        frontend_dist=tmp_path / "frontend",
        session_size=20,
        focus_size=5,
        admin_username="admin",
        admin_password_hash=hash_password("test-admin-password"),
    )
    app = create_app(settings, lessons=[lesson])
    with TestClient(app) as test_client:
        yield test_client


def register(client: TestClient) -> None:
    response = client.post("/api/learner/init", headers=HEADERS)
    assert response.status_code == 200, response.text


def test_auth_csrf_login_logout(client: TestClient) -> None:
    assert (
        client.post(
            "/api/auth/register", json={"username": "lan", "password": "password123"}
        ).status_code
        == 403
    )
    register(client)
    assert client.get("/api/auth/me").status_code == 410
    for path in ("login", "register", "logout"):
        assert client.post(f"/api/auth/{path}", headers=HEADERS).status_code == 410
    assert client.get("/api/admin/overview").status_code == 401
    login = client.post(
        "/api/admin/login",
        headers=HEADERS,
        json={"username": "admin", "password": "test-admin-password"},
    )
    assert login.status_code == 200
    assert "HttpOnly" in login.headers["set-cookie"]
    overview = client.get("/api/admin/overview")
    assert overview.status_code == 200
    assert overview.json()["visitors_total"] == 1
    assert sum(row["visits"] for row in overview.json()["visits_by_day"]) == 1
    assert overview.headers["cache-control"] == "no-store"
    client.post("/api/admin/logout", headers=HEADERS)
    assert client.get("/api/admin/overview").status_code == 401


def test_admin_login_rate_limit(client: TestClient) -> None:
    for count in range(5):
        response = client.post(
            "/api/admin/login",
            headers=HEADERS,
            json={"username": "admin", "password": "incorrect"},
        )
        assert response.status_code == (429 if count == 4 else 401)


def test_lessons_session_answer_and_double_submit(client: TestClient) -> None:
    register(client)
    assert client.get("/api/lessons").json()["lessons"][0]["item_count"] == 25
    session_response = client.post(
        "/api/sessions", headers=HEADERS, json={"lesson_slug": "hiragana"}
    )
    assert session_response.status_code == 201, session_response.text
    session = session_response.json()
    assert len(session["questions"]) == 20
    question = session["questions"][0]
    answer = client.post(
        f"/api/sessions/{session['id']}/answers",
        headers=HEADERS,
        json={"position": question["position"], "answer": "wrong"},
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["progress"]["weakness"] == 2
    again = client.post(
        f"/api/sessions/{session['id']}/answers",
        headers=HEADERS,
        json={"position": question["position"], "answer": "wrong"},
    )
    assert again.status_code == 409
    assert (
        client.post(
            f"/api/sessions/{session['id']}/answers",
            headers=HEADERS,
            json={"position": 20, "answer": "x"},
        ).status_code
        == 422
    )
    summary = client.get(f"/api/sessions/{session['id']}/summary")
    assert summary.status_code == 200
    assert summary.json()["next_focus"][0]["weakness"] == 2


def test_learner_accounts_are_disabled_even_if_registration_flag_is_set(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'closed.db'}",
        content_dir=tmp_path,
        allow_registration=True,
    )
    with TestClient(create_app(settings, lessons=[])) as client:
        response = client.post(
            "/api/auth/register",
            headers=HEADERS,
            json={"username": "lan", "password": "password123"},
        )
        assert response.status_code == 410
        assert client.get("/api/config").json()["registration_open"] is False


def test_anonymous_cookie_is_stable_and_isolates_progress(client: TestClient) -> None:
    first = client.post("/api/learner/init", headers=HEADERS)
    cookie = first.cookies.get("jp_learner")
    assert cookie
    set_cookie = first.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie
    again = client.post("/api/learner/init", headers=HEADERS)
    assert "set-cookie" not in again.headers

    session = client.post("/api/sessions", headers=HEADERS, json={"lesson_slug": "hiragana"}).json()
    question = session["questions"][0]
    client.post(
        f"/api/sessions/{session['id']}/answers",
        headers=HEADERS,
        json={"position": question["position"], "answer": "?"},
    )
    mine = client.get("/api/lessons").json()["lessons"][0]
    assert mine["progress"]["total_answers"] == 1
    assert mine["active_session_id"] == session["id"]

    with TestClient(client.app) as other:
        assert other.post("/api/learner/init", headers=HEADERS).cookies.get("jp_learner") != cookie
        theirs = other.get("/api/lessons").json()["lessons"][0]
        assert theirs["progress"]["total_answers"] == 0
        assert theirs["active_session_id"] is None
        assert other.get(f"/api/sessions/{session['id']}").status_code == 404
        assert other.get("/api/sessions").json()["sessions"] == []


def test_forged_learner_cookie_gets_a_fresh_identity(client: TestClient) -> None:
    client.cookies.set("jp_learner", "forged-token")
    response = client.post("/api/learner/init", headers=HEADERS)
    assert response.status_code == 200
    assert response.cookies.get("jp_learner") not in (None, "forged-token")


def test_admin_overview_is_aggregate_only(client: TestClient) -> None:
    register(client)
    session = client.post("/api/sessions", headers=HEADERS, json={"lesson_slug": "hiragana"}).json()
    for question in session["questions"][:3]:
        client.post(
            f"/api/sessions/{session['id']}/answers",
            headers=HEADERS,
            json={"position": question["position"], "answer": "a"},
        )
    with TestClient(client.app) as other:
        register(other)

    learner_cookie = client.cookies.get("jp_learner")
    # The learner cookie alone never grants admin access.
    assert client.get("/api/admin/overview").status_code == 401
    login = client.post(
        "/api/admin/login",
        headers=HEADERS,
        json={"username": "admin", "password": "test-admin-password"},
    )
    assert "samesite=strict" in login.headers["set-cookie"].lower()
    assert "path=/api/admin" in login.headers["set-cookie"].lower()
    body = client.get("/api/admin/overview").json()
    assert set(body) == {
        "visitors_total",
        "active_learners_7d",
        "active_sessions_15m",
        "questions_in_sessions",
        "answers_submitted",
        "visits_by_day",
    }
    assert body["visitors_total"] == 2
    assert body["active_learners_7d"] == 2
    assert body["active_sessions_15m"] == 1
    assert body["questions_in_sessions"] == 20
    assert body["answers_submitted"] == 3
    assert len(body["visits_by_day"]) == 30
    assert body["visits_by_day"][-1]["visits"] == 2
    assert all(set(row) == {"date", "visits"} for row in body["visits_by_day"])
    raw = client.get("/api/admin/overview").text
    assert learner_cookie not in raw and "anon-" not in raw and "testclient" not in raw


def test_admin_login_requires_configuration(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'noadmin.db'}",
        content_dir=tmp_path,
    )
    with TestClient(create_app(settings, lessons=[])) as client:
        response = client.post(
            "/api/admin/login", headers=HEADERS, json={"username": "admin", "password": "x"}
        )
        assert response.status_code == 503
        assert client.get("/api/admin/overview").status_code == 401


def test_wrong_admin_username_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/admin/login",
        headers=HEADERS,
        json={"username": "root", "password": "test-admin-password"},
    )
    assert response.status_code == 401
    assert client.get("/api/admin/overview").status_code == 401


def test_completed_session_counts(client: TestClient) -> None:
    register(client)
    session = client.post("/api/sessions", headers=HEADERS, json={"lesson_slug": "hiragana"}).json()
    last = None
    for question in session["questions"]:
        last = client.post(
            f"/api/sessions/{session['id']}/answers",
            headers=HEADERS,
            json={"position": question["position"], "answer": "?"},
        )
        assert last.status_code == 200, last.text
    assert last is not None
    assert last.json()["session"] == {
        "status": "completed",
        "total": 20,
        "answered_count": 20,
        "correct_count": 0,
    }


def test_spa_fallback_security_headers_and_unknown_api(client: TestClient, tmp_path: Path) -> None:
    frontend = client.app.state.settings.frontend_dist
    frontend.mkdir()
    (frontend / "index.html").write_text("<html>app</html>", encoding="utf-8")
    response = client.get("/study")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    unknown = client.get("/api/unknown")
    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "Không tìm thấy đường dẫn."}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
