"""Kana -> romaji conversion and lenient answer checking.

Content stores readings as kana only. For every reading we build a regular
expression that accepts the spellings learners commonly type: Hepburn
(``shi``, ``tsu``, ``ja``), Kunrei/Nihon-shiki (``si``, ``tu``, ``zya``),
IME-style input (``nn`` for ん), macrons (``tōkyō``) and ``-`` for ー.

Public API (other modules depend on these names; keep them stable):

- ``to_romaji(reading) -> str``: canonical display romaji, e.g. ``gakkou``.
- ``romaji_options(readings) -> list[str]``: canonical romaji per reading, deduplicated.
- ``is_correct(readings, answer) -> bool``: whether the answer matches any reading.
- ``unsupported_characters(reading) -> set[str]``: characters the converter cannot read.
- ``UnsupportedReadingError``: raised when a reading contains unknown characters.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from itertools import product

VOWELS = "aeiou"
MAX_ANSWER_LENGTH = 200
_MAX_VARIANTS = 64


class UnsupportedReadingError(ValueError):
    """A reading contains a character that is not kana, ー, a space or ・."""


def _row(kana: str, *romaji: str) -> dict[str, tuple[str, ...]]:
    return {k: (r,) for k, r in zip(kana, romaji, strict=True)}


# First alternative is the canonical (Hepburn) spelling shown to the learner.
_SINGLE: dict[str, tuple[str, ...]] = {
    **_row("あいうえお", "a", "i", "u", "e", "o"),
    **_row("かきくけこ", "ka", "ki", "ku", "ke", "ko"),
    **_row("さすせそ", "sa", "su", "se", "so"),
    **_row("たてと", "ta", "te", "to"),
    **_row("なにぬねの", "na", "ni", "nu", "ne", "no"),
    **_row("はひへほ", "ha", "hi", "he", "ho"),
    **_row("まみむめも", "ma", "mi", "mu", "me", "mo"),
    **_row("やゆよ", "ya", "yu", "yo"),
    **_row("らりるれろ", "ra", "ri", "ru", "re", "ro"),
    **_row("わ", "wa"),
    **_row("がぎぐげご", "ga", "gi", "gu", "ge", "go"),
    **_row("ざずぜぞ", "za", "zu", "ze", "zo"),
    **_row("だでど", "da", "de", "do"),
    **_row("ばびぶべぼ", "ba", "bi", "bu", "be", "bo"),
    **_row("ぱぴぷぺぽ", "pa", "pi", "pu", "pe", "po"),
    "し": ("shi", "si"),
    "ち": ("chi", "ti"),
    "つ": ("tsu", "tu"),
    "ふ": ("fu", "hu"),
    "じ": ("ji", "zi"),
    "ぢ": ("ji", "di", "zi"),
    "づ": ("zu", "du"),
    "を": ("wo", "o"),
    "ゐ": ("wi", "i"),
    "ゑ": ("we", "e"),
    "ん": ("n", "nn"),
    "ゔ": ("vu",),
    # Katakana-only letters with no hiragana counterpart.
    "ヷ": ("va",),
    "ヸ": ("vi",),
    "ヹ": ("ve",),
    "ヺ": ("vo",),
    # Small kana standing alone (not part of a digraph).
    "ぁ": ("a", "xa", "la"),
    "ぃ": ("i", "xi", "li"),
    "ぅ": ("u", "xu", "lu"),
    "ぇ": ("e", "xe", "le"),
    "ぉ": ("o", "xo", "lo"),
    "ゃ": ("ya", "xya", "lya"),
    "ゅ": ("yu", "xyu", "lyu"),
    "ょ": ("yo", "xyo", "lyo"),
    "ゎ": ("wa", "xwa", "lwa"),
    "ゕ": ("ka", "xka", "lka"),
    "ゖ": ("ke", "xke", "lke"),
}

_DIGRAPHS: dict[str, tuple[str, ...]] = {}
for _kana, _consonant in {
    "き": "k",
    "ぎ": "g",
    "に": "n",
    "ひ": "h",
    "み": "m",
    "り": "r",
    "び": "b",
    "ぴ": "p",
}.items():
    for _small, _vowel in zip("ゃゅょ", "auo", strict=True):
        _DIGRAPHS[_kana + _small] = (f"{_consonant}y{_vowel}",)
for _small, _vowel in zip("ゃゅょ", "auo", strict=True):
    _DIGRAPHS["し" + _small] = (f"sh{_vowel}", f"sy{_vowel}")
    _DIGRAPHS["ち" + _small] = (f"ch{_vowel}", f"ty{_vowel}", f"cy{_vowel}")
    _DIGRAPHS["じ" + _small] = (f"j{_vowel}", f"zy{_vowel}", f"jy{_vowel}")
    _DIGRAPHS["ぢ" + _small] = (f"j{_vowel}", f"dy{_vowel}", f"zy{_vowel}")
_DIGRAPHS.update(
    {
        # Extended combinations, mostly used in katakana loanwords.
        "しぇ": ("she", "sye"),
        "じぇ": ("je", "zye", "jye"),
        "ちぇ": ("che", "tye", "cye"),
        "ふぁ": ("fa",),
        "ふぃ": ("fi",),
        "ふぇ": ("fe",),
        "ふぉ": ("fo",),
        "ふゅ": ("fyu",),
        "てぃ": ("ti", "thi"),
        "でぃ": ("di", "dhi"),
        "てゅ": ("tyu", "thu"),
        "でゅ": ("dyu", "dhu"),
        "とぅ": ("tu", "twu"),
        "どぅ": ("du", "dwu"),
        "うぃ": ("wi",),
        "うぇ": ("we",),
        "うぉ": ("wo",),
        "いぇ": ("ye",),
        "つぁ": ("tsa",),
        "つぃ": ("tsi",),
        "つぇ": ("tse",),
        "つぉ": ("tso",),
        "ゔぁ": ("va",),
        "ゔぃ": ("vi",),
        "ゔぇ": ("ve",),
        "ゔぉ": ("vo",),
        "ゔゅ": ("vyu",),
        "くぁ": ("kwa", "qa"),
        "くぃ": ("kwi", "qi"),
        "くぇ": ("kwe", "qe"),
        "くぉ": ("kwo", "qo"),
        "ぐぁ": ("gwa",),
        "すぃ": ("si",),
        "ずぃ": ("zi",),
    }
)

_SOKUON = "っ"
_CHOON = "ー"
_IGNORED = frozenset(" ・")


@dataclass
class _Unit:
    kana: str
    alts: tuple[str, ...]


def _to_hiragana(text: str) -> str:
    """Normalize width and map katakana (ァ..ヶ) to hiragana; ー and ヷ..ヺ are kept."""
    text = unicodedata.normalize("NFKC", text)
    return "".join(chr(ord(ch) - 0x60) if 0x30A1 <= ord(ch) <= 0x30F6 else ch for ch in text)


def unsupported_characters(reading: str) -> set[str]:
    text = _to_hiragana(reading)
    known = set(_SINGLE) | {_SOKUON, _CHOON} | _IGNORED
    return {ch for ch in text if ch not in known}


def _first_letters(alts: tuple[str, ...]) -> list[str]:
    letters: list[str] = []
    for alt in alts:
        options = ("t", "c") if alt.startswith("ch") else (alt[:1],)
        for letter in options:
            if letter and letter not in VOWELS and letter not in letters:
                letters.append(letter)
    return letters


@lru_cache(maxsize=4096)
def _units(reading: str) -> tuple[_Unit, ...]:
    text = _to_hiragana(reading)
    bad = unsupported_characters(reading)
    if bad:
        raise UnsupportedReadingError(
            f"Unsupported characters {sorted(bad)!r} in reading {reading!r}"
        )

    units: list[_Unit] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in _IGNORED:
            units.append(_Unit(" ", ("",)))
            i += 1
            continue
        pair = text[i : i + 2]
        if len(pair) == 2 and pair in _DIGRAPHS:
            units.append(_Unit(pair, _DIGRAPHS[pair]))
            i += 2
            continue
        units.append(_Unit(ch, _SINGLE.get(ch, ())))
        i += 1

    # Pass 1 (left to right): long-vowel mark and おう-style long vowels.
    for j, unit in enumerate(units):
        prev = units[j - 1] if j > 0 else None
        if unit.kana == _CHOON:
            vowels: list[str] = []
            for alt in prev.alts if prev else ():
                if alt and alt[-1] in VOWELS and alt[-1] not in vowels:
                    vowels.append(alt[-1])
            unit.alts = (*vowels, "-")
        elif (
            unit.kana == "う" and prev and prev.alts and all(alt.endswith("o") for alt in prev.alts)
        ):
            unit.alts = ("u", "o")
        elif (
            unit.kana == "い" and prev and prev.alts and all(alt.endswith("e") for alt in prev.alts)
        ):
            unit.alts = ("i", "e")

    # Pass 2 (right to left): small tsu doubles the next consonant; ん before b/p/m may be m.
    for j in range(len(units) - 1, -1, -1):
        unit = units[j]
        nxt = units[j + 1] if j + 1 < len(units) else None
        if unit.kana == _SOKUON:
            letters = _first_letters(nxt.alts) if nxt and nxt.kana != _SOKUON else []
            unit.alts = tuple(letters) if letters else ("t", "")
        elif unit.kana == "ん" and nxt and nxt.alts and nxt.alts[0][:1] in ("b", "p", "m"):
            unit.alts = ("n", "nn", "m")

    return tuple(units)


def to_romaji(reading: str) -> str:
    """Canonical romaji for display, e.g. がっこう -> gakkou, コーヒー -> koohii."""
    units = _units(reading)
    parts: list[str] = []
    for j, unit in enumerate(units):
        if unit.kana == " ":
            if parts and parts[-1] != " ":
                parts.append(" ")
            continue
        text = unit.alts[0] if unit.alts else ""
        nxt = units[j + 1] if j + 1 < len(units) else None
        if unit.kana == "ん" and nxt and nxt.alts and nxt.alts[0][:1] in VOWELS + "y":
            text = "n'"
        parts.append(text)
    return "".join(parts).strip()


def romaji_options(readings: Iterable[str]) -> list[str]:
    options: list[str] = []
    for reading in readings:
        romaji = to_romaji(reading)
        if romaji not in options:
            options.append(romaji)
    return options


@lru_cache(maxsize=4096)
def _pattern(reading: str) -> re.Pattern[str]:
    groups = "".join(
        "(?:" + "|".join(re.escape(alt) for alt in unit.alts) + ")"
        for unit in _units(reading)
        if unit.kana != " "
    )
    return re.compile(groups)


_DASHES = str.maketrans({ch: "-" for ch in "ー‐‑‒–—―−"})
_STRIP = re.compile(r"[\s'’‘`´\".,!?;:、。！？・()（）]")
_MACRONS: dict[str, tuple[str, ...]] = {
    "ā": ("aa",),
    "â": ("aa",),
    "ī": ("ii",),
    "î": ("ii",),
    "ū": ("uu",),
    "û": ("uu",),
    "ē": ("ee", "ei"),
    "ê": ("ee", "ei"),
    "ō": ("ou", "oo"),
    "ô": ("ou", "oo"),
}


def answer_variants(answer: str) -> list[str]:
    """Normalize a typed answer; macrons expand to every doubled-vowel spelling."""
    text = unicodedata.normalize("NFKC", answer[:MAX_ANSWER_LENGTH]).lower()
    text = _STRIP.sub("", text.translate(_DASHES))
    if not text:
        return []
    pieces = [_MACRONS.get(ch, (ch,)) for ch in text]
    variants: list[str] = []
    for combo in product(*pieces):
        variants.append("".join(combo))
        if len(variants) >= _MAX_VARIANTS:
            break
    return variants


def is_correct(readings: Iterable[str], answer: str) -> bool:
    variants = answer_variants(answer)
    if not variants:
        return False
    for reading in readings:
        pattern = _pattern(reading)
        if any(pattern.fullmatch(variant) for variant in variants):
            return True
    return False
