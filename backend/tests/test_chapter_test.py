from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.content.validation import load_lessons
from app.main import create_app
from app.services.audio import AudioLibrary, load_audio_library
from app.services.chapter_test import (
    CHAPTERS,
    PARTS,
    QUESTION_COUNT,
    Candidate,
    NotEnoughContent,
    audio_candidates,
    generate_test,
    is_available,
)
from app.services.listening import (
    EXCLUDED_KANA,
    char_distractors,
    is_katakana,
    sound_key,
    split_morae,
    to_hiragana,
    word_distractors,
)

HEADERS = {"X-Requested-With": "jp-practice"}
CHAPTER = CHAPTERS[1]
LESSONS = [lesson for lesson in load_lessons() if lesson.slug in CHAPTER.lesson_slugs]

def _candidates() -> list[Candidate]:
    candidates = []
    next_id = 1
    for lesson in LESSONS:
        for item in lesson.items:
            candidates.append(Candidate(next_id, lesson.slug, item.prompt, item.kind))
            next_id += 1
    return candidates

CANDIDATES = _candidates()
EXPECTED_PARTS = {
    "hiragana-char": 3,
    "hiragana-word": 15,
    "katakana-char": 3,
    "katakana-youon": 1,
    "katakana-word": 8,
}

def _all_audio(_: str) -> bool:
    return True

def test_split_morae_and_sound_key() -> None:
    assert split_morae("きょうしつ") == ["きょ", "う", "し", "つ"]
    assert split_morae("タクシー") == ["た", "く", "し", "ー"]
    assert sound_key("べんきょう") == sound_key("べんきょお")
    assert sound_key("とけい") == sound_key("とけえ")
    assert sound_key("はさみ") != sound_key("はすみ")

def test_word_distractors_are_distinct_misspellings_in_the_same_script() -> None:
    rng = random.Random(1)
    words = ("はさみ", "けっこん", "びょうき", "しゅくだい", "タクシー", "ペット", "コンビニ")
    for answer in words:
        for _ in range(20):
            options = word_distractors(answer, rng)
            assert len(options) == 3
            keys = {sound_key(option) for option in [answer, *options]}
            assert len(keys) == 4, (answer, options)
            assert all(is_katakana(option) == is_katakana(answer) for option in options)
            assert not any(set(to_hiragana(option)) & EXCLUDED_KANA for option in options)

def test_char_distractors_prefer_look_alikes() -> None:
    pool = list("あいうえおかきくけこさしすせそたちつてとらりるれろ")
    options = char_distractors("る", pool, random.Random(3))
    assert len(options) == 3
    assert set(options) <= set("うらろつ")
    katakana = char_distractors("マ", list("アイウエオマミムメモヤユヨ"), random.Random(3))
    assert set(katakana) <= set("ムアヤ")

def test_generated_test_mirrors_the_paper_layout() -> None:
    questions = generate_test(CANDIDATES, _all_audio, random.Random(42))
    assert len(questions) == QUESTION_COUNT == 30
    assert Counter(question.part for question in questions) == EXPECTED_PARTS
    order = [part.key for part in PARTS]
    assert [question.part for question in questions] == sorted(
        (question.part for question in questions), key=order.index
    )
    by_id = {candidate.item_id: candidate for candidate in CANDIDATES}
    assert len({question.prompt for question in questions}) == 30
    for question in questions:
        assert len(question.options) == 4
        assert question.options[question.answer_index] == question.prompt
        assert len({sound_key(option) for option in question.options}) == 4
        assert by_id[question.item_id].prompt == question.prompt
        assert not set(to_hiragana(question.prompt)) & EXCLUDED_KANA

def test_every_attempt_differs_and_avoids_the_previous_items() -> None:
    rng = random.Random()
    first = generate_test(CANDIDATES, _all_audio, rng)
    second = generate_test(CANDIDATES, _all_audio, rng, avoid={q.item_id for q in first})
    assert {q.item_id for q in first}.isdisjoint({q.item_id for q in second})
    answer_slots = {tuple(q.answer_index for q in generate_test(CANDIDATES, _all_audio, rng))
                    for _ in range(5)}
    assert len(answer_slots) == 5

def test_missing_audio_makes_the_test_unavailable() -> None:
    assert is_available(CANDIDATES, _all_audio)
    assert not is_available(CANDIDATES, lambda prompt: not is_katakana(prompt))
    with pytest.raises(NotEnoughContent):
        generate_test(CANDIDATES, lambda prompt: not is_katakana(prompt), random.Random(0))

def test_shipped_audio_covers_every_question() -> None:
    library = load_audio_library()
    assert library.credit == "VOICEVOX:四国めたん"
    missing = [c.prompt for c in audio_candidates(CANDIDATES) if not library.has(c.prompt)]
    assert missing == []
    audio_dir = Path(__file__).resolve().parents[2] / "frontend" / "public" / "assets" / "audio"
    assert all((audio_dir / name).is_file() for name in library.clips.values())

@pytest.fixture
def client(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        content_dir=tmp_path / "empty-lessons",
        frontend_dist=tmp_path / "frontend",
    )
    audio = AudioLibrary(
        credit="VOICEVOX:四国めたん",
        clips={candidate.prompt: f"{index}.mp3" for index, candidate in enumerate(CANDIDATES)},
    )
    app = create_app(settings, lessons=LESSONS, audio=audio)
    with TestClient(app) as test_client:
        assert test_client.post("/api/learner/init", headers=HEADERS).status_code == 200
        yield test_client

def _start(client: TestClient) -> dict:
    response = client.post("/api/chapters/1/tests", headers=HEADERS)
    assert response.status_code == 201, response.text
    return response.json()

def test_chapter_list_and_start(client: TestClient) -> None:
    chapters = client.get("/api/chapters").json()["chapters"]
    assert chapters[0]["chapter"] == 1
    assert chapters[0]["available"] is True
    assert chapters[0]["question_count"] == 30
    assert chapters[0]["attempts"] == 0
    assert client.post("/api/chapters/9/tests", headers=HEADERS).status_code == 404

    test = _start(client)
    assert test["status"] == "active"
    assert test["total"] == 30
    assert test["correct_count"] is None
    assert test["audio_credit"] == "VOICEVOX:四国めたん"
    question = test["questions"][0]
    assert set(question) == {"position", "part", "part_label", "audio_url", "options", "choice"}
    assert question["audio_url"].startswith("/assets/audio/")
    assert client.get("/api/chapters").json()["chapters"][0]["active_test_id"] == test["id"]

def test_answers_can_change_until_submit(client: TestClient) -> None:
    test = _start(client)
    url = f"/api/tests/{test['id']}"
    first = client.put(f"{url}/answers", headers=HEADERS, json={"position": 0, "choice": 1})
    assert first.status_code == 200
    assert first.json() == {"position": 0, "choice": 1, "total": 30, "answered_count": 1}
    changed = client.put(f"{url}/answers", headers=HEADERS, json={"position": 0, "choice": 2})
    assert changed.json()["answered_count"] == 1
    assert client.get(url).json()["questions"][0]["choice"] == 2
    bad_position = client.put(f"{url}/answers", headers=HEADERS, json={"position": 30, "choice": 0})
    assert bad_position.status_code == 422
    bad_choice = client.put(f"{url}/answers", headers=HEADERS, json={"position": 1, "choice": 4})
    assert bad_choice.status_code == 422
    assert client.get(f"{url}/result").status_code == 409

def test_submit_scores_and_reveals(client: TestClient) -> None:
    test = _start(client)
    url = f"/api/tests/{test['id']}"
    # Without the key the client cannot know the answers; read it from the database instead.
    from app.models import ChapterTestQuestion

    with client.app.state.session_factory() as db:
        keys = {
            row.position: row.answer_index
            for row in db.query(ChapterTestQuestion).filter_by(test_id=test["id"])
        }
    for position in range(20):
        choice = keys[position] if position < 15 else (keys[position] + 1) % 4
        client.put(f"{url}/answers", headers=HEADERS, json={"position": position, "choice": choice})
    result = client.post(f"{url}/submit", headers=HEADERS)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["test"]["status"] == "completed"
    assert body["test"]["correct_count"] == 15
    assert body["test"]["answered_count"] == 20
    assert sum(part["total"] for part in body["parts"]) == 30
    assert sum(part["correct"] for part in body["parts"]) == 15
    unanswered = body["questions"][25]
    assert unanswered["choice"] is None and unanswered["is_correct"] is False
    assert client.post(f"{url}/submit", headers=HEADERS).status_code == 409
    late = client.put(f"{url}/answers", headers=HEADERS, json={"position": 25, "choice": 0})
    assert late.status_code == 409
    assert client.get(f"{url}/result").json()["test"]["correct_count"] == 15
    info = client.get("/api/chapters").json()["chapters"][0]
    assert (info["attempts"], info["best_score"], info["last_score"]) == (1, 15, 15)
    assert info["active_test_id"] is None

def test_new_attempt_abandons_the_old_one_and_changes_questions(client: TestClient) -> None:
    first = _start(client)
    second = _start(client)
    assert client.get(f"/api/tests/{first['id']}").json()["status"] == "abandoned"
    first_prompts = {tuple(q["options"]) for q in first["questions"]}
    second_prompts = {tuple(q["options"]) for q in second["questions"]}
    assert first_prompts.isdisjoint(second_prompts)

def test_tests_are_private_and_need_csrf(client: TestClient, tmp_path: Path) -> None:
    test = _start(client)
    assert client.post("/api/chapters/1/tests").status_code == 403
    assert client.get("/api/tests/not-a-uuid").status_code == 404
    client.cookies.clear()
    assert client.post("/api/learner/init", headers=HEADERS).status_code == 200
    assert client.get(f"/api/tests/{test['id']}").status_code == 404
    answer = client.put(
        f"/api/tests/{test['id']}/answers", headers=HEADERS, json={"position": 0, "choice": 0}
    )
    assert answer.status_code == 404

def test_without_audio_the_chapter_is_unavailable(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        content_dir=tmp_path / "empty-lessons",
        frontend_dist=tmp_path / "frontend",
    )
    app = create_app(settings, lessons=LESSONS, audio=AudioLibrary())
    with TestClient(app) as client:
        client.post("/api/learner/init", headers=HEADERS)
        assert client.get("/api/chapters").json()["chapters"][0]["available"] is False
        assert client.post("/api/chapters/1/tests", headers=HEADERS).status_code == 503
