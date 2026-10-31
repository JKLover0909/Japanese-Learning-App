from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from app.config import Settings
from app.content.schema import ContentItem, LessonFile
from app.content.validation import LESSONS_DIR, _hiragana, load_lessons
from app.main import create_app
from app.models import Item, ItemProgress, Lesson


def test_schema_rejects_blank_after_strip() -> None:
    with pytest.raises(ValidationError):
        ContentItem(key="blank-prompt", prompt="   ", readings=["あ"], kind="char")
    with pytest.raises(ValidationError):
        ContentItem(key="blank-reading", prompt="あ", readings=["  "], kind="char")


def test_kana_normalization_handles_width_and_decomposed_dakuten() -> None:
    assert _hiragana("ガ") == _hiragana("が")
    assert _hiragana("ｶﾞ") == _hiragana("が")


def test_real_lesson_files() -> None:
    if len(list(Path(LESSONS_DIR).glob("*.json"))) < 5:
        pytest.skip("lesson files are still being authored")
    lessons = load_lessons(LESSONS_DIR)
    assert len(lessons) == 6
    assert next(lesson for lesson in lessons if lesson.slug == "greetings").items
    assert len(next(lesson for lesson in lessons if lesson.slug == "numbers").items) == 100


def _lesson(slug: str, position: int, items: list[dict]) -> LessonFile:
    return LessonFile(slug=slug, position=position, title=slug, description=slug, items=items)


GREETING = {
    "key": "konnichiwa",
    "prompt": "こんにちは",
    "readings": ["こんにちは"],
    "kind": "phrase",
    "meaning": "Xin chào",
}
NUMBER = {"key": "n-1", "prompt": "1", "readings": ["いち"], "kind": "number"}


def test_split_sync_moves_legacy_items_and_keeps_history(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'split.db'}",
        content_dir=tmp_path,
        session_size=2,
        focus_size=1,
    )
    headers = {"X-Requested-With": "jp-practice"}
    legacy = _lesson("greetings-numbers", 5, [GREETING, NUMBER])
    with TestClient(create_app(settings, lessons=[legacy])) as client:
        client.post("/api/learner/init", headers=headers)
        session = client.post(
            "/api/sessions", headers=headers, json={"lesson_slug": "greetings-numbers"}
        ).json()
        for question in session["questions"]:
            client.post(
                f"/api/sessions/{session['id']}/answers",
                headers=headers,
                json={"position": question["position"], "answer": "?"},
            )
        learner_cookie = client.cookies.get("jp_learner")
        factory = client.app.state.session_factory
        with factory() as db:
            before = {item.key: item.id for item in db.scalars(select(Item))}

    split = [_lesson("greetings", 5, [GREETING]), _lesson("numbers", 6, [NUMBER])]
    for _ in range(2):  # the second start must be a no-op
        with TestClient(create_app(settings, lessons=split)) as client:
            client.cookies.set("jp_learner", learner_cookie)
            lessons = {row["slug"]: row for row in client.get("/api/lessons").json()["lessons"]}
            assert list(lessons) == ["greetings", "numbers"]
            assert lessons["greetings"]["progress"]["total_answers"] == 1
            assert lessons["numbers"]["progress"]["total_answers"] == 1
            history = client.get(f"/api/sessions/{session['id']}/summary")
            assert history.status_code == 200
            assert len(history.json()["wrong"]) == 2
            with client.app.state.session_factory() as db:
                items = {item.key: item for item in db.scalars(select(Item))}
                assert {key: item.id for key, item in items.items()} == before
                lesson_slugs = {lesson.id: lesson.slug for lesson in db.scalars(select(Lesson))}
                assert lesson_slugs[items["konnichiwa"].lesson_id] == "greetings"
                assert lesson_slugs[items["n-1"].lesson_id] == "numbers"
                legacy_row = db.scalar(select(Lesson).where(Lesson.slug == "greetings-numbers"))
                assert legacy_row is not None and not legacy_row.is_active
                assert db.scalar(select(func.count(ItemProgress.item_id))) == 2
