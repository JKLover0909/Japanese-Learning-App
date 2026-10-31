"""Pydantic models for lesson content files (``app/content/lessons/*.json``)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ItemKind = Literal["char", "word", "phrase", "number"]

KEY_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class ContentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=KEY_PATTERN, max_length=64)
    """Stable identifier within the lesson. Never rename: progress is keyed by it."""
    prompt: str = Field(min_length=1, max_length=64)
    """Text shown to the learner (kana, or digits for numbers)."""
    readings: list[str] = Field(min_length=1, max_length=6)
    """Phonetic kana readings. The first one is canonical and shown as the answer."""
    kind: ItemKind
    meaning: str | None = Field(default=None, max_length=160)
    """Vietnamese meaning. Required for words and phrases."""
    tags: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("prompt", "readings")
    @classmethod
    def _strip(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("text must not be blank")
            return value
        values = [reading.strip() for reading in value]
        if any(not reading for reading in values):
            raise ValueError("readings must not contain blank values")
        return values


class LessonFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    slug: str = Field(pattern=SLUG_PATTERN, max_length=64)
    position: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=400)
    items: list[ContentItem] = Field(min_length=1)
