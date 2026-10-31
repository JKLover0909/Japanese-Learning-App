"""Load and validate lesson content files.

``load_lessons(directory)`` is what the application uses. It raises
``ContentError`` listing every problem, so a broken content file stops
startup instead of silently serving bad questions.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from app.content.schema import LessonFile
from app.services.romaji import to_romaji, unsupported_characters

LESSONS_DIR = Path(__file__).parent / "lessons"


def _normalize_kana(text: str) -> str:
    """Normalize Unicode width and decomposed dakuten for content comparisons."""
    return unicodedata.normalize("NFC", unicodedata.normalize("NFKC", text))


def _katakana(text: str) -> str:
    text = _normalize_kana(text)
    return "".join(chr(ord(ch) + 0x60) if 0x3041 <= ord(ch) <= 0x3096 else ch for ch in text)


def _hiragana(text: str) -> str:
    text = _normalize_kana(text)
    return "".join(chr(ord(ch) - 0x60) if 0x30A1 <= ord(ch) <= 0x30F6 else ch for ch in text)


BASIC_HIRAGANA = (
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
)
DAKUTEN_HIRAGANA = "がぎぐげござじずぜぞだぢづでどばびぶべぼ"
HANDAKUTEN_HIRAGANA = "ぱぴぷぺぽ"
SMALL_HIRAGANA = "ぁぃぅぇぉゃゅょゎっ"
YOUON_HIRAGANA = [base + small for base in "きしちにひみりぎじびぴ" for small in "ゃゅょ"]

BASIC_KATAKANA = _katakana(BASIC_HIRAGANA)
DAKUTEN_KATAKANA = _katakana(DAKUTEN_HIRAGANA) + "ヴ"
HANDAKUTEN_KATAKANA = _katakana(HANDAKUTEN_HIRAGANA)
SMALL_KATAKANA = _katakana(SMALL_HIRAGANA)
YOUON_KATAKANA = [_katakana(pair) for pair in YOUON_HIRAGANA]
EXTENDED_KATAKANA = [
    "ファ",
    "フィ",
    "フェ",
    "フォ",
    "ティ",
    "ディ",
    "ウィ",
    "ウェ",
    "ウォ",
    "シェ",
    "ジェ",
    "チェ",
    "ヴ",
    "ヴァ",
    "ヴィ",
    "ヴェ",
    "ヴォ",
]

ALL_HIRAGANA = BASIC_HIRAGANA + DAKUTEN_HIRAGANA + HANDAKUTEN_HIRAGANA + SMALL_HIRAGANA
ALL_KATAKANA = BASIC_KATAKANA + DAKUTEN_KATAKANA + HANDAKUTEN_KATAKANA + SMALL_KATAKANA + "ー"
LONG_VOWEL_ROMAJI = re.compile(r"aa|ii|uu|ee|oo|ou|ei")

MIN_ITEMS = 150
MAX_ITEMS = 260


class ContentError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Invalid lesson content:\n- " + "\n- ".join(problems))


def _has_extended_feature(prompt: str, script: str) -> bool:
    if script == "hiragana":
        special = DAKUTEN_HIRAGANA + HANDAKUTEN_HIRAGANA + SMALL_HIRAGANA
        if any(ch in special for ch in prompt):
            return True
        return bool(LONG_VOWEL_ROMAJI.search(to_romaji(prompt)))
    special = DAKUTEN_KATAKANA + HANDAKUTEN_KATAKANA + SMALL_KATAKANA + "ー"
    return any(ch in special for ch in prompt)


def _kana_lesson_rules(
    *, alphabet: str, required: list[str], script: str, extended: bool, min_words: int
) -> Callable[[LessonFile], list[str]]:
    def check(lesson: LessonFile) -> list[str]:
        problems: list[str] = []
        chars = {item.prompt for item in lesson.items if item.kind == "char"}
        missing = [ch for ch in required if ch not in chars]
        if missing:
            problems.append(f"missing char items: {' '.join(missing)}")
        words = [item for item in lesson.items if item.kind == "word"]
        if len(words) < min_words:
            problems.append(f"needs at least {min_words} word items, found {len(words)}")
        for item in lesson.items:
            where = f"item {item.key!r} ({item.prompt})"
            if item.kind not in ("char", "word"):
                problems.append(f"{where}: kind must be 'char' or 'word'")
            outside = sorted({ch for ch in item.prompt if ch not in alphabet})
            if outside:
                problems.append(f"{where}: characters not allowed in this lesson: {outside}")
            if _hiragana(item.prompt) != _hiragana(item.readings[0]):
                problems.append(f"{where}: first reading must spell the prompt exactly")
            if extended and item.kind == "word" and not _has_extended_feature(item.prompt, script):
                problems.append(
                    f"{where}: word has no dakuten/handakuten, digraph, small tsu or long vowel"
                )
        return problems

    return check


def _greetings_rules(lesson: LessonFile) -> list[str]:
    problems: list[str] = []
    phrases = [item for item in lesson.items if item.kind == "phrase"]
    if len(phrases) < 40:
        problems.append(f"needs at least 40 phrase items, found {len(phrases)}")
    allowed = set(ALL_HIRAGANA + ALL_KATAKANA + " 、。！？・")
    for item in lesson.items:
        where = f"item {item.key!r} ({item.prompt})"
        if item.kind != "phrase":
            problems.append(f"{where}: kind must be 'phrase'")
        outside = sorted({ch for ch in item.prompt if ch not in allowed})
        if outside:
            problems.append(f"{where}: characters not allowed in a phrase prompt: {outside}")
    return problems


def _numbers_rules(lesson: LessonFile) -> list[str]:
    problems: list[str] = []
    numbers = {item.prompt: item for item in lesson.items if item.kind == "number"}
    expected = {str(n) for n in range(1, 101)}
    if set(numbers) != expected:
        missing = sorted(expected - set(numbers), key=int)
        extra = sorted(set(numbers) - expected)
        problems.append(f"number items must be exactly 1..100 (missing {missing}, extra {extra})")
    if any(item.kind != "number" for item in lesson.items):
        problems.append("all items must have kind 'number'")
    return problems


def _generic_problems(lesson: LessonFile) -> list[str]:
    problems: list[str] = []
    if lesson.slug == "greetings":
        min_items = 40
    elif lesson.slug in {"numbers", "greetings-numbers"}:
        min_items = 1
    else:
        min_items = MIN_ITEMS
    if not min_items <= len(lesson.items) <= MAX_ITEMS:
        problems.append(f"has {len(lesson.items)} items; expected {min_items}..{MAX_ITEMS}")
    seen_keys: set[str] = set()
    seen_prompts: set[str] = set()
    for item in lesson.items:
        where = f"item {item.key!r} ({item.prompt})"
        if item.key in seen_keys:
            problems.append(f"{where}: duplicate key")
        seen_keys.add(item.key)
        if item.prompt in seen_prompts:
            problems.append(f"{where}: duplicate prompt")
        seen_prompts.add(item.prompt)
        if len(set(item.readings)) != len(item.readings):
            problems.append(f"{where}: duplicate readings")
        for reading in item.readings:
            bad = unsupported_characters(reading)
            if bad:
                problems.append(f"{where}: reading {reading!r} has unsupported chars {sorted(bad)}")
        if item.kind in ("word", "phrase") and not (item.meaning and item.meaning.strip()):
            problems.append(f"{where}: words and phrases need a Vietnamese meaning")
    return problems


LESSON_RULES: dict[str, Callable[[LessonFile], list[str]]] = {
    "hiragana": _kana_lesson_rules(
        alphabet=BASIC_HIRAGANA,
        required=list(BASIC_HIRAGANA),
        script="hiragana",
        extended=False,
        min_words=120,
    ),
    "hiragana-extended": _kana_lesson_rules(
        alphabet=ALL_HIRAGANA,
        required=list(DAKUTEN_HIRAGANA + HANDAKUTEN_HIRAGANA) + YOUON_HIRAGANA,
        script="hiragana",
        extended=True,
        min_words=110,
    ),
    "katakana": _kana_lesson_rules(
        alphabet=BASIC_KATAKANA,
        required=list(BASIC_KATAKANA),
        script="katakana",
        extended=False,
        min_words=100,
    ),
    "katakana-extended": _kana_lesson_rules(
        alphabet=ALL_KATAKANA,
        required=list(DAKUTEN_KATAKANA[:-1] + HANDAKUTEN_KATAKANA)
        + YOUON_KATAKANA
        + EXTENDED_KATAKANA,
        script="katakana",
        extended=True,
        min_words=100,
    ),
    "greetings": _greetings_rules,
    "numbers": _numbers_rules,
}


def validate_lesson(lesson: LessonFile) -> list[str]:
    problems = _generic_problems(lesson)
    rules = LESSON_RULES.get(lesson.slug)
    if rules is None:
        problems.append(f"unknown lesson slug {lesson.slug!r}; add rules in validation.py")
    else:
        problems.extend(rules(lesson))
    return [f"{lesson.slug}: {problem}" for problem in problems]


def load_lessons(directory: Path = LESSONS_DIR) -> list[LessonFile]:
    """Parse and validate every ``*.json`` file in ``directory``, sorted by position."""
    lessons: list[LessonFile] = []
    problems: list[str] = []
    for path in sorted(Path(directory).glob("*.json")):
        try:
            lesson = LessonFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValidationError) as exc:
            problems.append(f"{path.name}: {exc}")
            continue
        problems.extend(validate_lesson(lesson))
        lessons.append(lesson)
    slugs = [lesson.slug for lesson in lessons]
    positions = [lesson.position for lesson in lessons]
    if len(set(slugs)) != len(slugs):
        problems.append(f"duplicate lesson slugs: {slugs}")
    if len(set(positions)) != len(positions):
        problems.append(f"duplicate lesson positions: {positions}")
    if problems:
        raise ContentError(problems)
    return sorted(lessons, key=lambda lesson: lesson.position)
