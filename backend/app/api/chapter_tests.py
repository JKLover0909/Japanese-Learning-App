"""End-of-chapter listening tests: start, answer, submit and review."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from app.api.deps import AnonymousLearner, Database
from app.api.schemas import (
    ChapterListResponse,
    ChapterTestAnswerOut,
    ChapterTestAnswerRequest,
    ChapterTestDetailOut,
    ChapterTestInfoOut,
    ChapterTestPartScoreOut,
    ChapterTestQuestionOut,
    ChapterTestResultOut,
    ChapterTestResultQuestionOut,
)
from app.models import (
    SESSION_ABANDONED,
    SESSION_ACTIVE,
    SESSION_COMPLETED,
    ChapterTest,
    ChapterTestQuestion,
    Item,
    Lesson,
)
from app.services.audio import AudioLibrary
from app.services.chapter_test import (
    CHAPTERS,
    PART_LABELS,
    PARTS,
    QUESTION_COUNT,
    Candidate,
    Chapter,
    NotEnoughContent,
    generate_test,
    is_available,
)

router = APIRouter(tags=["chapter-tests"])

_NOT_FOUND = "Không tìm thấy bài kiểm tra."
_NOT_ACTIVE = "Bài kiểm tra đã kết thúc."

def _audio(request: Request) -> AudioLibrary:
    return request.app.state.audio

def _chapter(number: int) -> Chapter:
    chapter = CHAPTERS.get(number)
    if chapter is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương.")
    return chapter

def _candidates(db: Database, chapter: Chapter) -> list[Candidate]:
    rows = db.execute(
        select(Item.id, Lesson.slug, Item.prompt, Item.kind)
        .join(Lesson, Item.lesson_id == Lesson.id)
        .where(
            Lesson.slug.in_(chapter.lesson_slugs),
            Lesson.is_active.is_(True),
            Item.is_active.is_(True),
        )
        .order_by(Item.id)
    )
    return [
        Candidate(item_id=id_, lesson_slug=slug, prompt=prompt, kind=kind)
        for id_, slug, prompt, kind in rows
    ]

def _get_owned_test(db: Database, user_id: int, test_id: str) -> ChapterTest:
    try:
        parsed = str(uuid.UUID(test_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail=_NOT_FOUND) from None
    test = db.scalar(
        select(ChapterTest)
        .options(selectinload(ChapterTest.questions).joinedload(ChapterTestQuestion.item))
        .where(ChapterTest.id == parsed, ChapterTest.user_id == user_id)
    )
    if test is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return test

def _detail(test: ChapterTest, audio: AudioLibrary) -> ChapterTestDetailOut:
    chapter = CHAPTERS.get(test.chapter)
    submitted = test.status == SESSION_COMPLETED
    return ChapterTestDetailOut(
        id=test.id,
        chapter=test.chapter,
        title=chapter.title if chapter else f"Chương {test.chapter}",
        status=test.status,
        total=test.total,
        answered_count=test.answered_count,
        correct_count=test.correct_count if submitted else None,
        created_at=test.created_at,
        completed_at=test.completed_at,
        audio_credit=audio.credit,
        questions=[
            ChapterTestQuestionOut(
                position=question.position,
                part=question.part,
                part_label=PART_LABELS.get(question.part, question.part),
                audio_url=audio.url(question.item.prompt),
                options=list(question.options),
                choice=question.choice,
            )
            for question in test.questions
        ],
    )

@router.get("/chapters", response_model=ChapterListResponse)
def list_chapters(db: Database, user: AnonymousLearner, request: Request) -> dict[str, Any]:
    audio = _audio(request)
    chapters = []
    for chapter in CHAPTERS.values():
        scores = db.execute(
            select(func.count(), func.max(ChapterTest.correct_count)).where(
                ChapterTest.user_id == user.id,
                ChapterTest.chapter == chapter.number,
                ChapterTest.status == SESSION_COMPLETED,
            )
        ).one()
        last_score = db.scalar(
            select(ChapterTest.correct_count)
            .where(
                ChapterTest.user_id == user.id,
                ChapterTest.chapter == chapter.number,
                ChapterTest.status == SESSION_COMPLETED,
            )
            .order_by(ChapterTest.completed_at.desc())
            .limit(1)
        )
        active_id = db.scalar(
            select(ChapterTest.id)
            .where(
                ChapterTest.user_id == user.id,
                ChapterTest.chapter == chapter.number,
                ChapterTest.status == SESSION_ACTIVE,
            )
            .order_by(ChapterTest.created_at.desc())
            .limit(1)
        )
        chapters.append(
            ChapterTestInfoOut(
                chapter=chapter.number,
                title=chapter.title,
                lesson_slugs=list(chapter.lesson_slugs),
                question_count=QUESTION_COUNT,
                available=is_available(_candidates(db, chapter), audio.has),
                active_test_id=active_id,
                attempts=scores[0],
                best_score=scores[1],
                last_score=last_score,
                audio_credit=audio.credit,
            )
        )
    return {"chapters": chapters}

@router.post(
    "/chapters/{chapter_number}/tests", response_model=ChapterTestDetailOut, status_code=201
)
def create_test(
    chapter_number: int, db: Database, user: AnonymousLearner, request: Request
) -> ChapterTestDetailOut:
    chapter = _chapter(chapter_number)
    audio = _audio(request)
    # Prefer items the learner did not hear in their previous attempt.
    previous = db.scalar(
        select(ChapterTest.id)
        .where(ChapterTest.user_id == user.id, ChapterTest.chapter == chapter.number)
        .order_by(ChapterTest.created_at.desc())
        .limit(1)
    )
    avoid = set(
        db.scalars(
            select(ChapterTestQuestion.item_id).where(ChapterTestQuestion.test_id == previous)
        )
    )
    try:
        planned = generate_test(_candidates(db, chapter), audio.has, random.Random(), avoid)
    except NotEnoughContent:
        raise HTTPException(
            status_code=503, detail="Chưa đủ nội dung hoặc âm thanh để tạo bài kiểm tra."
        ) from None
    db.execute(
        update(ChapterTest)
        .where(
            ChapterTest.user_id == user.id,
            ChapterTest.chapter == chapter.number,
            ChapterTest.status == SESSION_ACTIVE,
        )
        .values(status=SESSION_ABANDONED)
    )
    test = ChapterTest(
        id=str(uuid.uuid4()),
        user_id=user.id,
        chapter=chapter.number,
        status=SESSION_ACTIVE,
        total=len(planned),
        answered_count=0,
        correct_count=0,
        created_at=datetime.now(UTC),
    )
    db.add(test)
    db.flush()
    for position, question in enumerate(planned):
        db.add(
            ChapterTestQuestion(
                test_id=test.id,
                position=position,
                part=question.part,
                item_id=question.item_id,
                options=question.options,
                answer_index=question.answer_index,
            )
        )
    db.commit()
    return _detail(_get_owned_test(db, user.id, test.id), audio)

@router.get("/tests/{test_id}", response_model=ChapterTestDetailOut)
def get_test(
    test_id: str, db: Database, user: AnonymousLearner, request: Request
) -> ChapterTestDetailOut:
    return _detail(_get_owned_test(db, user.id, test_id), _audio(request))

@router.put("/tests/{test_id}/answers", response_model=ChapterTestAnswerOut)
def answer_test(
    test_id: str, body: ChapterTestAnswerRequest, db: Database, user: AnonymousLearner
) -> dict[str, Any]:
    """Circle (or change) an option. Nothing is scored or revealed until the test is submitted."""
    test = _get_owned_test(db, user.id, test_id)
    if test.status != SESSION_ACTIVE:
        raise HTTPException(status_code=409, detail=_NOT_ACTIVE)
    if body.position >= test.total:
        raise HTTPException(status_code=422, detail="Vị trí câu hỏi không hợp lệ.")
    question = test.questions[body.position]
    if body.choice >= len(question.options):
        raise HTTPException(status_code=422, detail="Lựa chọn không hợp lệ.")
    now = datetime.now(UTC)
    try:
        changed = db.execute(
            update(ChapterTestQuestion)
            .where(
                ChapterTestQuestion.id == question.id,
                ChapterTestQuestion.test_id.in_(
                    select(ChapterTest.id).where(
                        ChapterTest.id == test.id, ChapterTest.status == SESSION_ACTIVE
                    )
                ),
            )
            .values(choice=body.choice, answered_at=now)
        )
        if changed.rowcount != 1:
            raise HTTPException(status_code=409, detail=_NOT_ACTIVE)
        answered = db.scalar(
            select(func.count()).where(
                ChapterTestQuestion.test_id == test.id, ChapterTestQuestion.choice.is_not(None)
            )
        )
        db.execute(
            update(ChapterTest)
            .where(ChapterTest.id == test.id, ChapterTest.status == SESSION_ACTIVE)
            .values(answered_count=answered)
        )
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    return {
        "position": body.position,
        "choice": body.choice,
        "total": test.total,
        "answered_count": answered,
    }

@router.post("/tests/{test_id}/submit", response_model=ChapterTestResultOut)
def submit_test(
    test_id: str, db: Database, user: AnonymousLearner, request: Request
) -> dict[str, Any]:
    """Hand the test in: unanswered questions count as wrong."""
    test = _get_owned_test(db, user.id, test_id)
    if test.status != SESSION_ACTIVE:
        raise HTTPException(status_code=409, detail=_NOT_ACTIVE)
    now = datetime.now(UTC)
    try:
        # Lock first so the score is computed from the final choices (SQLite serializes writers).
        locked = db.execute(
            update(ChapterTest)
            .where(ChapterTest.id == test.id, ChapterTest.status == SESSION_ACTIVE)
            .values(status=SESSION_COMPLETED, completed_at=now)
        )
        if locked.rowcount != 1:
            raise HTTPException(status_code=409, detail=_NOT_ACTIVE)
        rows = list(
            db.execute(
                select(
                    ChapterTestQuestion.id,
                    ChapterTestQuestion.choice,
                    ChapterTestQuestion.answer_index,
                ).where(ChapterTestQuestion.test_id == test.id)
            )
        )
        correct = 0
        answered = 0
        for question_id, choice, answer_index in rows:
            is_right = choice == answer_index
            correct += int(is_right)
            answered += int(choice is not None)
            db.execute(
                update(ChapterTestQuestion)
                .where(ChapterTestQuestion.id == question_id)
                .values(is_correct=is_right)
            )
        db.execute(
            update(ChapterTest)
            .where(ChapterTest.id == test.id)
            .values(correct_count=correct, answered_count=answered)
        )
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    db.expire_all()
    return _result(_get_owned_test(db, user.id, test.id), _audio(request))

@router.get("/tests/{test_id}/result", response_model=ChapterTestResultOut)
def test_result(
    test_id: str, db: Database, user: AnonymousLearner, request: Request
) -> dict[str, Any]:
    test = _get_owned_test(db, user.id, test_id)
    if test.status != SESSION_COMPLETED:
        raise HTTPException(status_code=409, detail="Bài kiểm tra chưa được nộp.")
    return _result(test, _audio(request))

def _result(test: ChapterTest, audio: AudioLibrary) -> dict[str, Any]:
    parts = []
    for part in PARTS:
        questions = [question for question in test.questions if question.part == part.key]
        if questions:
            parts.append(
                ChapterTestPartScoreOut(
                    part=part.key,
                    label=part.label,
                    correct=sum(bool(question.is_correct) for question in questions),
                    total=len(questions),
                )
            )
    return {
        "test": _detail(test, audio),
        "parts": parts,
        "questions": [
            ChapterTestResultQuestionOut(
                position=question.position,
                part=question.part,
                part_label=PART_LABELS.get(question.part, question.part),
                audio_url=audio.url(question.item.prompt),
                options=list(question.options),
                choice=question.choice,
                answer_index=question.answer_index,
                is_correct=bool(question.is_correct),
                meaning=question.item.meaning,
            )
            for question in test.questions
        ],
    }
