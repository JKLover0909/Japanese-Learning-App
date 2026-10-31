"""Practice session creation, answering and summaries."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload, selectinload

from app.api.deps import AnonymousLearner, Database
from app.api.schemas import (
    AnswerRequest,
    AnswerResultOut,
    AnswerSessionOut,
    ItemProgressOut,
    NextFocusOut,
    QuestionOut,
    QuestionResultOut,
    SessionCreateRequest,
    SessionDetailOut,
    SessionLessonOut,
    SessionListItemOut,
    SessionListResponse,
    SessionSummaryOut,
    WrongAnswerOut,
)
from app.models import (
    SESSION_ABANDONED,
    SESSION_ACTIVE,
    SESSION_COMPLETED,
    Item,
    ItemProgress,
    Lesson,
    PracticeSession,
    SessionQuestion,
)
from app.services.progress import focus_items, record_answer
from app.services.romaji import is_correct, romaji_options
from app.services.selection import select_questions

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _get_owned_session(db: Database, user_id: int, session_id: str) -> PracticeSession:
    try:
        parsed = str(uuid.UUID(session_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt luyện tập.") from None
    session = db.scalar(
        select(PracticeSession)
        .options(
            joinedload(PracticeSession.lesson),
            selectinload(PracticeSession.questions).joinedload(SessionQuestion.item),
        )
        .where(PracticeSession.id == parsed, PracticeSession.user_id == user_id)
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt luyện tập.")
    return session


def _detail(session: PracticeSession) -> SessionDetailOut:
    questions = []
    for question in session.questions:
        result = None
        if question.answer is not None:
            result = QuestionResultOut(
                answer=question.answer,
                is_correct=bool(question.is_correct),
                expected_romaji=romaji_options(question.item.readings),
                expected_readings=list(question.item.readings),
            )
        questions.append(
            QuestionOut(
                position=question.position,
                prompt=question.item.prompt,
                kind=question.item.kind,
                meaning=question.item.meaning,
                is_focus=question.is_focus,
                answered=question.answer is not None,
                result=result,
            )
        )
    return SessionDetailOut(
        id=session.id,
        lesson=SessionLessonOut(slug=session.lesson.slug, title=session.lesson.title),
        status=session.status,
        total=session.total,
        answered_count=session.answered_count,
        correct_count=session.correct_count,
        focus_count=session.focus_count,
        created_at=session.created_at,
        completed_at=session.completed_at,
        questions=questions,
    )


def _progress_out(row: ItemProgress) -> ItemProgressOut:
    return ItemProgressOut(
        seen_count=row.seen_count,
        correct_count=row.correct_count,
        wrong_count=row.wrong_count,
        weakness=row.weakness,
        streak=row.streak,
        last_seen_at=row.last_seen_at,
    )


@router.post("", response_model=SessionDetailOut, status_code=201)
def create_session(
    body: SessionCreateRequest,
    db: Database,
    user: AnonymousLearner,
    request: Request,
) -> SessionDetailOut:
    lesson = db.scalar(
        select(Lesson).where(Lesson.slug == body.lesson_slug, Lesson.is_active.is_(True))
    )
    if lesson is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài học.")

    now = datetime.now(UTC)
    db.execute(
        update(PracticeSession)
        .where(
            PracticeSession.user_id == user.id,
            PracticeSession.lesson_id == lesson.id,
            PracticeSession.status == SESSION_ACTIVE,
        )
        .values(status=SESSION_ABANDONED)
    )
    items = list(
        db.scalars(
            select(Item)
            .where(Item.lesson_id == lesson.id, Item.is_active.is_(True))
            .order_by(Item.position)
        )
    )
    progress = (
        {
            row.item_id: row
            for row in db.scalars(
                select(ItemProgress).where(
                    ItemProgress.user_id == user.id,
                    ItemProgress.item_id.in_([item.id for item in items]),
                )
            )
        }
        if items
        else {}
    )
    sizes = request.app.state.settings
    selected = select_questions(
        items,
        progress,
        random.Random(),
        session_size=sizes.session_size,
        focus_size=sizes.focus_size,
    )
    session = PracticeSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        lesson_id=lesson.id,
        status=SESSION_ACTIVE,
        total=len(selected),
        answered_count=0,
        correct_count=0,
        focus_count=sum(question.is_focus for question in selected),
        created_at=now,
    )
    db.add(session)
    db.flush()
    for selected_question in selected:
        db.add(
            SessionQuestion(
                session_id=session.id,
                position=selected_question.position,
                item_id=selected_question.item.id,
                is_focus=selected_question.is_focus,
            )
        )
    db.commit()
    return _detail(_get_owned_session(db, user.id, session.id))


@router.get("", response_model=SessionListResponse)
def list_sessions(
    db: Database,
    user: AnonymousLearner,
    lesson_slug: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    query = (
        select(PracticeSession)
        .options(joinedload(PracticeSession.lesson))
        .where(PracticeSession.user_id == user.id)
        .order_by(PracticeSession.created_at.desc())
        .limit(limit)
    )
    if lesson_slug is not None:
        query = query.join(Lesson).where(Lesson.slug == lesson_slug)
    rows = db.scalars(query)
    return {
        "sessions": [
            SessionListItemOut(
                id=row.id,
                lesson_slug=row.lesson.slug,
                lesson_title=row.lesson.title,
                status=row.status,
                total=row.total,
                answered_count=row.answered_count,
                correct_count=row.correct_count,
                created_at=row.created_at,
                completed_at=row.completed_at,
            )
            for row in rows
        ]
    }


@router.get("/{session_id}", response_model=SessionDetailOut)
def get_session(session_id: str, db: Database, user: AnonymousLearner) -> SessionDetailOut:
    return _detail(_get_owned_session(db, user.id, session_id))


@router.post("/{session_id}/answers", response_model=AnswerResultOut)
def answer_session(
    session_id: str, body: AnswerRequest, db: Database, user: AnonymousLearner
) -> dict[str, Any]:
    # Read only to identify the item and validate position; all state changes happen in a
    # transaction after the conditional answer UPDATE succeeds (double submits get 409).
    session = _get_owned_session(db, user.id, session_id)
    if session.status != SESSION_ACTIVE:
        raise HTTPException(status_code=409, detail="Lượt luyện tập không còn hoạt động.")
    if body.position >= session.total:
        raise HTTPException(status_code=422, detail="Vị trí câu hỏi không hợp lệ.")
    question = session.questions[body.position]
    if question.answer is not None:
        raise HTTPException(status_code=409, detail="Câu hỏi này đã được trả lời.")
    item = question.item
    is_right = is_correct(item.readings, body.answer)
    now = datetime.now(UTC)
    result = {
        "position": question.position,
        "is_correct": is_right,
        "answer": body.answer,
        "expected_romaji": romaji_options(item.readings),
        "expected_readings": list(item.readings),
        "meaning": item.meaning,
    }
    try:
        # Each write is conditional. SQLite serializes writers, so the session's old count
        # cannot be committed twice after another answer wins the race.
        if db.bind is not None and db.bind.dialect.name == "sqlite":
            db.execute(
                update(PracticeSession)
                .where(PracticeSession.id == session.id)
                .values(answered_count=PracticeSession.answered_count)
            )
        won = db.execute(
            update(SessionQuestion)
            .where(
                SessionQuestion.id == question.id,
                SessionQuestion.answer.is_(None),
                SessionQuestion.session_id == session.id,
            )
            .values(answer=body.answer, is_correct=is_right, answered_at=now)
        )
        if won.rowcount != 1:
            raise HTTPException(status_code=409, detail="Câu hỏi này đã được trả lời.")
        new_answered = session.answered_count + 1
        new_correct = session.correct_count + int(is_right)
        completed = new_answered == session.total
        changed = db.execute(
            update(PracticeSession)
            .where(
                PracticeSession.id == session.id,
                PracticeSession.status == SESSION_ACTIVE,
                PracticeSession.answered_count == new_answered - 1,
            )
            .values(
                answered_count=new_answered,
                correct_count=new_correct,
                status=SESSION_COMPLETED if completed else SESSION_ACTIVE,
                completed_at=now if completed else None,
            )
        )
        if changed.rowcount != 1:
            raise HTTPException(status_code=409, detail="Lượt luyện tập không còn hoạt động.")
        progress = record_answer(db, user_id=user.id, item_id=item.id, is_correct=is_right, now=now)
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    result["progress"] = _progress_out(progress)
    result["session"] = AnswerSessionOut(
        status=SESSION_COMPLETED if completed else SESSION_ACTIVE,
        total=session.total,
        answered_count=new_answered,
        correct_count=new_correct,
    )
    return result


@router.get("/{session_id}/summary", response_model=SessionSummaryOut)
def session_summary(
    session_id: str,
    db: Database,
    user: AnonymousLearner,
    request: Request,
) -> dict[str, Any]:
    session = _get_owned_session(db, user.id, session_id)
    wrong = [
        WrongAnswerOut(
            position=question.position,
            prompt=question.item.prompt,
            kind=question.item.kind,
            meaning=question.item.meaning,
            answer=question.answer or "",
            expected_romaji=romaji_options(question.item.readings),
            expected_readings=list(question.item.readings),
        )
        for question in session.questions
        if question.answer is not None and not question.is_correct
    ]
    all_items = list(
        db.scalars(
            select(Item)
            .where(Item.lesson_id == session.lesson_id, Item.is_active.is_(True))
            .order_by(Item.position)
        )
    )
    progress_by_item_id = (
        {
            row.item_id: row
            for row in db.scalars(
                select(ItemProgress).where(
                    ItemProgress.user_id == user.id,
                    ItemProgress.item_id.in_([item.id for item in all_items]),
                )
            )
        }
        if all_items
        else {}
    )
    focus = focus_items(all_items, progress_by_item_id, request.app.state.settings.focus_size)
    next_focus = [
        NextFocusOut(
            key=item.key,
            prompt=item.prompt,
            kind=item.kind,
            weakness=progress_by_item_id[item.id].weakness,
        )
        for item in focus
    ]
    return {"session": _detail(session), "wrong": wrong, "next_focus": next_focus}
