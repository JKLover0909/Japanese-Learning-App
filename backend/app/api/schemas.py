"""Request and response schemas for the HTTP API contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(APIModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=64)
    registration_code: str | None = Field(default=None, max_length=256)

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("display_name cannot be blank")
        return value


class LoginRequest(APIModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=1, max_length=128)


class UserOut(APIModel):
    id: int
    username: str
    display_name: str
    created_at: datetime


class UserResponse(APIModel):
    user: UserOut


class ConfigResponse(APIModel):
    registration_open: bool
    registration_code_required: bool
    session_size: int
    focus_size: int


class ItemProgressOut(APIModel):
    seen_count: int
    correct_count: int
    wrong_count: int
    weakness: int
    streak: int
    last_seen_at: datetime | None


class LessonProgressOut(APIModel):
    seen_items: int
    weak_items: int
    mastered_items: int
    total_answers: int
    correct_answers: int
    accuracy: float | None


class LessonSummaryOut(APIModel):
    slug: str
    position: int
    title: str
    description: str
    item_count: int
    progress: LessonProgressOut
    active_session_id: str | None


class LessonListResponse(APIModel):
    lessons: list[LessonSummaryOut]


class LessonItemOut(APIModel):
    key: str
    prompt: str
    kind: Literal["char", "word", "phrase", "number"]
    meaning: str | None
    tags: list[str]
    readings: list[str]
    romaji: list[str]
    progress: ItemProgressOut | None


class LessonDetailOut(APIModel):
    lesson: LessonSummaryOut
    items: list[LessonItemOut]


class QuestionResultOut(APIModel):
    answer: str
    is_correct: bool
    expected_romaji: list[str]
    expected_readings: list[str]


class QuestionOut(APIModel):
    position: int
    prompt: str
    kind: Literal["char", "word", "phrase", "number"]
    meaning: str | None
    is_focus: bool
    answered: bool
    result: QuestionResultOut | None


class SessionLessonOut(APIModel):
    slug: str
    title: str


class SessionDetailOut(APIModel):
    id: str
    lesson: SessionLessonOut
    status: Literal["active", "completed", "abandoned"]
    total: int
    answered_count: int
    correct_count: int
    focus_count: int
    created_at: datetime
    completed_at: datetime | None
    questions: list[QuestionOut]


class SessionCreateRequest(APIModel):
    lesson_slug: str = Field(min_length=1, max_length=64)


class SessionListItemOut(APIModel):
    id: str
    lesson_slug: str
    lesson_title: str
    status: Literal["active", "completed", "abandoned"]
    total: int
    answered_count: int
    correct_count: int
    created_at: datetime
    completed_at: datetime | None


class SessionListResponse(APIModel):
    sessions: list[SessionListItemOut]


class AnswerRequest(APIModel):
    position: int = Field(ge=0)
    answer: str = Field(min_length=1, max_length=200)

    @field_validator("answer")
    @classmethod
    def trim_answer(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("answer cannot be empty")
        return value


class AnswerSessionOut(APIModel):
    status: Literal["active", "completed", "abandoned"]
    total: int
    answered_count: int
    correct_count: int


class AnswerResultOut(APIModel):
    position: int
    is_correct: bool
    answer: str
    expected_romaji: list[str]
    expected_readings: list[str]
    meaning: str | None
    progress: ItemProgressOut
    session: AnswerSessionOut


class WrongAnswerOut(APIModel):
    position: int
    prompt: str
    kind: Literal["char", "word", "phrase", "number"]
    meaning: str | None
    answer: str
    expected_romaji: list[str]
    expected_readings: list[str]


class NextFocusOut(APIModel):
    key: str
    prompt: str
    kind: Literal["char", "word", "phrase", "number"]
    weakness: int


class SessionSummaryOut(APIModel):
    session: SessionDetailOut
    wrong: list[WrongAnswerOut]
    next_focus: list[NextFocusOut]


TestStatus = Literal["active", "completed", "abandoned"]

class ChapterTestInfoOut(APIModel):
    chapter: int
    title: str
    lesson_slugs: list[str]
    question_count: int
    available: bool
    """False while the lessons or recorded audio cannot fill a whole test."""
    active_test_id: str | None
    attempts: int
    """Submitted tests."""
    best_score: int | None
    last_score: int | None
    audio_credit: str

class ChapterListResponse(APIModel):
    chapters: list[ChapterTestInfoOut]

class ChapterTestQuestionOut(APIModel):
    position: int
    part: str
    part_label: str
    audio_url: str | None
    options: list[str]
    choice: int | None

class ChapterTestDetailOut(APIModel):
    id: str
    chapter: int
    title: str
    status: TestStatus
    total: int
    answered_count: int
    correct_count: int | None
    """Hidden (null) until the test is submitted."""
    created_at: datetime
    completed_at: datetime | None
    audio_credit: str
    questions: list[ChapterTestQuestionOut]

class ChapterTestAnswerRequest(APIModel):
    position: int = Field(ge=0)
    choice: int = Field(ge=0, le=3)

class ChapterTestAnswerOut(APIModel):
    position: int
    choice: int
    total: int
    answered_count: int

class ChapterTestPartScoreOut(APIModel):
    part: str
    label: str
    correct: int
    total: int

class ChapterTestResultQuestionOut(APIModel):
    position: int
    part: str
    part_label: str
    audio_url: str | None
    options: list[str]
    choice: int | None
    answer_index: int
    is_correct: bool
    meaning: str | None

class ChapterTestResultOut(APIModel):
    test: ChapterTestDetailOut
    parts: list[ChapterTestPartScoreOut]
    questions: list[ChapterTestResultQuestionOut]

class HealthResponse(APIModel):
    status: Literal["ok"] = "ok"
