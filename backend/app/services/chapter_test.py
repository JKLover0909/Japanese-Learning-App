"""End-of-chapter listening tests: chapter definitions and question generation.

A test mirrors the paper "listen and circle" test used in class: the learner hears a
kana or a word and picks it from four written options. Its 30 questions come in five
parts, in this order:

1. 3 single hiragana          (2 basic, 1 voiced)
2. 15 hiragana words          (5 from the basic lesson, 10 from the extended one)
3. 3 single katakana
4. 1 katakana contracted sound (キャ, シュ…)
5. 8 katakana words           (3 basic, 5 extended)

Questions are shuffled within their part. Every attempt draws new items, new distractors
and a new option order; items from the learner's previous attempt are avoided when the
pool allows it.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from app.services.listening import (
    EXCLUDED_KANA,
    char_distractors,
    shuffled_options,
    to_hiragana,
    word_distractors,
)

OPTION_COUNT = 4

@dataclass(frozen=True)
class Chapter:
    number: int
    title: str
    lesson_slugs: tuple[str, ...]

CHAPTERS: dict[int, Chapter] = {
    1: Chapter(
        number=1,
        title="Chương 1: Hiragana, Katakana và chào hỏi",
        lesson_slugs=(
            "hiragana", "hiragana-extended", "katakana", "katakana-extended", "greetings",
        ),
    ),
}

@dataclass(frozen=True)
class Candidate:
    """An active lesson item that could become a question."""

    item_id: int
    lesson_slug: str
    prompt: str
    kind: str

def _single(candidate: Candidate) -> bool:
    # ん on its own is only a hum, too ambiguous to recognize by ear.
    return (
        candidate.kind == "char" and len(candidate.prompt) == 1 and candidate.prompt not in "んン"
    )

def _youon(candidate: Candidate) -> bool:
    return (
        candidate.kind == "char"
        and len(candidate.prompt) == 2
        and candidate.prompt[1] in "ゃゅょャュョ"
    )

def _word(candidate: Candidate) -> bool:
    return candidate.kind == "word"

@dataclass(frozen=True)
class Section:
    lesson: str
    count: int
    accept: Callable[[Candidate], bool]
    distractor_pool: str | None = None
    """Char sections draw distractors from this named pool; words generate misspellings."""

@dataclass(frozen=True)
class Part:
    key: str
    label: str
    sections: tuple[Section, ...]

# Candidates feeding each char distractor pool: (lesson, filter).
_POOLS: dict[str, tuple[tuple[str, Callable[[Candidate], bool]], ...]] = {
    "hiragana": (("hiragana", _single), ("hiragana-extended", _single)),
    "katakana": (("katakana", _single), ("katakana-extended", _single)),
    "katakana-youon": (("katakana-extended", _youon),),
}

PARTS: tuple[Part, ...] = (
    Part("hiragana-char", "Hiragana: chữ đơn", (
        Section("hiragana", 2, _single, "hiragana"),
        Section("hiragana-extended", 1, _single, "hiragana"),
    )),
    Part("hiragana-word", "Hiragana: từ", (
        Section("hiragana", 5, _word),
        Section("hiragana-extended", 10, _word),
    )),
    Part("katakana-char", "Katakana: chữ đơn", (
        Section("katakana", 3, _single, "katakana"),
    )),
    Part("katakana-youon", "Katakana: âm ghép", (
        Section("katakana-extended", 1, _youon, "katakana-youon"),
    )),
    Part("katakana-word", "Katakana: từ", (
        Section("katakana", 3, _word),
        Section("katakana-extended", 5, _word),
    )),
)
PART_LABELS = {part.key: part.label for part in PARTS}
QUESTION_COUNT = sum(section.count for part in PARTS for section in part.sections)

@dataclass(frozen=True)
class PlannedQuestion:
    part: str
    item_id: int
    prompt: str
    options: list[str]
    answer_index: int

class NotEnoughContent(Exception):
    """The lessons or audio clips cannot fill every part of the test."""

def is_listenable(candidate: Candidate, has_audio: Callable[[str], bool]) -> bool:
    """Items with を/ぢ/づ sound like other kana, so they are never asked."""
    return not set(to_hiragana(candidate.prompt)) & EXCLUDED_KANA and has_audio(candidate.prompt)

def audio_candidates(candidates: Iterable[Candidate]) -> list[Candidate]:
    """Items that can appear in a test of the chapter, so they need recorded audio."""
    by_lesson: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        by_lesson.setdefault(candidate.lesson_slug, []).append(candidate)
    wanted: dict[str, Candidate] = {}
    for part in PARTS:
        for section in part.sections:
            for candidate in by_lesson.get(section.lesson, []):
                if section.accept(candidate) and is_listenable(candidate, lambda _: True):
                    wanted.setdefault(candidate.prompt, candidate)
    return list(wanted.values())

def is_available(candidates: Sequence[Candidate], has_audio: Callable[[str], bool]) -> bool:
    """Whether every section has enough listenable items with distinct prompts."""
    by_lesson: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        by_lesson.setdefault(candidate.lesson_slug, []).append(candidate)
    for part in PARTS:
        for section in part.sections:
            prompts = {
                candidate.prompt
                for candidate in by_lesson.get(section.lesson, [])
                if section.accept(candidate) and is_listenable(candidate, has_audio)
            }
            if len(prompts) < section.count:
                return False
    return True

def generate_test(
    candidates: Sequence[Candidate],
    has_audio: Callable[[str], bool],
    rng: random.Random,
    avoid: Iterable[int] = (),
) -> list[PlannedQuestion]:
    """Plan a full test. Raises ``NotEnoughContent`` if any section cannot be filled."""
    avoid = set(avoid)
    by_lesson: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        by_lesson.setdefault(candidate.lesson_slug, []).append(candidate)
    pools = {
        name: [
            candidate.prompt
            for lesson, accept in sources
            for candidate in by_lesson.get(lesson, [])
            if accept(candidate)
        ]
        for name, sources in _POOLS.items()
    }
    used_prompts: set[str] = set()
    planned: list[PlannedQuestion] = []
    for part in PARTS:
        part_questions: list[PlannedQuestion] = []
        for section in part.sections:
            eligible = [
                candidate
                for candidate in by_lesson.get(section.lesson, [])
                if section.accept(candidate)
                and is_listenable(candidate, has_audio)
                and candidate.prompt not in used_prompts
            ]
            fresh = [candidate for candidate in eligible if candidate.item_id not in avoid]
            repeat = [candidate for candidate in eligible if candidate.item_id in avoid]
            rng.shuffle(fresh)
            rng.shuffle(repeat)
            taken = 0
            for candidate in [*fresh, *repeat]:
                if taken == section.count:
                    break
                if section.distractor_pool is None:
                    distractors = word_distractors(candidate.prompt, rng, OPTION_COUNT - 1)
                else:
                    distractors = char_distractors(
                        candidate.prompt, pools[section.distractor_pool], rng, OPTION_COUNT - 1
                    )
                if len(distractors) < OPTION_COUNT - 1:
                    continue
                options, answer_index = shuffled_options(candidate.prompt, distractors, rng)
                part_questions.append(
                    PlannedQuestion(
                        part.key, candidate.item_id, candidate.prompt, options, answer_index
                    )
                )
                used_prompts.add(candidate.prompt)
                taken += 1
            if taken < section.count:
                raise NotEnoughContent(
                    f"{part.key}: only {taken} of {section.count} questions from {section.lesson!r}"
                )
        rng.shuffle(part_questions)
        planned.extend(part_questions)
    return planned
