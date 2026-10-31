"""Distractor options for listen-and-choose questions.

A chapter test plays a kana or a word and shows four written options, like the paper
tests used in class: the real one and three near misses. Near misses imitate what a
listener confuses: another vowel or a similar consonant (はさみ/はすみ, さんぽ/さんば), a
missing or misplaced っ/ん/long vowel (けっこん/けこん, よっか/よおか, タクシー/タークシ),
and a split or flattened contracted sound (びょうき/びよき, しゅくだい/すくだい).

Every option set follows these rules:

- options are written in the answer's script and use only kana the chapter teaches;
- no two options sound alike (``sound_key``), so a careful listener always has exactly
  one right choice: を/お, ぢ/じ, づ/ず, おう/おお and えい/ええ count as the same sound;
- randomness comes from an injected ``random.Random``, so callers decide on seeding.
"""

from __future__ import annotations

import random
import unicodedata
from collections.abc import Iterable

from app.services.romaji import UnsupportedReadingError, to_romaji

VOWELS = "aeiou"
SOKUON = "っ"
HATSUON = "ん"
CHOON = "ー"
_SPECIAL = (SOKUON, HATSUON, CHOON)
_SMALL = "ゃゅょぁぃぅぇぉ"
_VOWEL_KANA = {"あ": "a", "い": "i", "う": "u", "え": "e", "お": "o"}
_SAME_SOUND = str.maketrans({"を": "お", "ぢ": "じ", "づ": "ず"})
EXCLUDED_KANA = frozenset("をぢづゔゎ")
"""Kana never used in listening questions or options: they sound like other kana or are rare."""

# Gojūon rows: a changed vowel stays in the row a learner recites (さ -> し, た -> つ).
_ROWS = [
    "あいうえお", "かきくけこ", "がぎぐげご", "さしすせそ", "ざじずぜぞ", "たちつてと", "だでど",
    "なにぬねの", "はひふへほ", "ばびぶべぼ", "ぱぴぷぺぽ", "まみむめも", "やゆよ", "らりるれろ",
]
_ROW_OF = {kana: row for row in _ROWS for kana in row}
_YOUON = [base + small for base in "きしちにひみりぎじびぴ" for small in "ゃゅょ"]
_FOREIGN = [
    "ふぁ", "ふぃ", "ふぇ", "ふぉ", "てぃ", "でぃ", "うぃ", "うぇ", "うぉ", "しぇ", "じぇ", "ちぇ",
]

# Consonants a listener mixes up; "" is a bare vowel.
_NEIGHBOURS: dict[str, tuple[str, ...]] = {
    "": ("h", "w", "y"),
    "k": ("g", "h"),
    "g": ("k", "z"),
    "s": ("z", "sh"),
    "z": ("s", "j", "d", "g"),
    "sh": ("s", "j", "ch"),
    "j": ("z", "sh", "ch"),
    "t": ("d", "ch"),
    "d": ("t", "z", "r"),
    "ch": ("j", "sh", "ts"),
    "ts": ("s", "ch", "z"),
    "n": ("m", "r"),
    "h": ("b", "p", "f", "w"),
    "f": ("h", "b", "p"),
    "b": ("p", "h", "d", "m"),
    "p": ("b", "h"),
    "m": ("n", "b"),
    "y": ("", "w"),
    "r": ("n", "d"),
    "w": ("h", ""),
    "ky": ("gy", "hy"),
    "gy": ("ky", "j"),
    "ny": ("my", "ry"),
    "hy": ("by", "py", "ky"),
    "by": ("py", "hy"),
    "py": ("by", "hy"),
    "my": ("ny", "by"),
    "ry": ("ny", "j"),
}
# A contracted sound without its glide: しゅ -> す, ちゅ -> つ, きょ -> こ.
_UNGLIDE = {"ky": "k", "gy": "g", "sh": "s", "j": "z", "ch": "ts", "ny": "n", "hy": "h",
            "by": "b", "py": "p", "my": "m", "ry": "r"}
# Hiragana spelling that lengthens each vowel (えい and おう are the usual long e/o).
_LONG_KANA = {"a": "あ", "i": "い", "u": "う", "e": "い", "o": "う"}
_GEMINATE = ("k", "s", "t", "c", "p")
"""Consonant starts that may follow っ in native words; katakana also allows voiced ones."""
_GEMINATE_KATAKANA = (*_GEMINATE, "g", "z", "d", "b", "j", "f")

# Characters that look alike in print. Single-character questions draw from these first.
HIRAGANA_SHAPES = [
    "うらろるつ", "さきちら", "てそひと", "はほまけ", "ねれわ", "あおめぬ", "いりこに",
    "しつ", "くへ", "なた", "すむ", "のめ", "ゆや", "えん", "よま",
]
KATAKANA_SHAPES = [
    "ワラウクフ", "ムマアヤ", "レノクト", "シツンソ", "コユヨロ", "チテナ", "スヌ", "ケク",
    "セヤ", "オホ", "ミシ", "タク", "エニ", "メナ",
]

# How often each kind of mistake is drawn when a word offers several.
_KIND_WEIGHTS = {"vowel": 3, "consonant": 3, "youon": 3, "special": 4, "insert": 1}
_MAX_PER_KIND = 2

def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", unicodedata.normalize("NFKC", text))

def to_hiragana(text: str) -> str:
    """Katakana to hiragana; ー is kept."""
    return "".join(
        chr(ord(ch) - 0x60) if 0x30A1 <= ord(ch) <= 0x30F6 else ch for ch in _normalize(text)
    )

def to_katakana(text: str) -> str:
    return "".join(
        chr(ord(ch) + 0x60) if 0x3041 <= ord(ch) <= 0x3096 else ch for ch in _normalize(text)
    )

def is_katakana(text: str) -> bool:
    return any(0x30A1 <= ord(ch) <= 0x30F6 for ch in text)

def split_morae(text: str) -> list[str]:
    """Split kana into hiragana morae: きょう -> [きょ, う]; っ, ん and ー stand alone."""
    morae: list[str] = []
    for ch in to_hiragana(text):
        if ch in _SMALL and morae and morae[-1] not in _SPECIAL:
            morae[-1] += ch
        else:
            morae.append(ch)
    return morae

def sound_key(text: str) -> str:
    """What the text sounds like. Options with the same key cannot share a question."""
    romaji = to_romaji(to_hiragana(text).translate(_SAME_SOUND))
    return romaji.replace("ou", "oo").replace("ei", "ee")

def _phones(mora: str) -> tuple[str, str] | None:
    """(consonant, vowel) of a regular mora, e.g. しゃ -> ("sh", "a"); None for っ/ん/ー."""
    if mora in _SPECIAL:
        return None
    try:
        romaji = to_romaji(mora)
    except UnsupportedReadingError:
        return None
    if not romaji or romaji[-1] not in VOWELS:
        return None
    return romaji[:-1], romaji[-1]

def _inventory(morae: Iterable[str]) -> dict[tuple[str, str], str]:
    table: dict[tuple[str, str], str] = {}
    for mora in morae:
        if set(mora) & EXCLUDED_KANA:
            continue
        phones = _phones(mora)
        if phones is not None:
            table.setdefault(phones, mora)
    return table

_SINGLE_KANA = [kana for row in _ROWS for kana in row] + ["わ"]
_HIRAGANA_MORAE = _inventory([*_SINGLE_KANA, *_YOUON])
_KATAKANA_MORAE = _inventory([*_SINGLE_KANA, *_YOUON, *_FOREIGN])

def _vowel_before(morae: list[str], index: int) -> str | None:
    """Vowel heard just before ``index`` (skipping back over ー), or None after っ/ん."""
    index -= 1
    while index >= 0:
        phones = _phones(morae[index])
        if phones is not None:
            return phones[1]
        if morae[index] != CHOON:
            return None
        index -= 1
    return None

def _lengthens(morae: list[str], index: int) -> bool:
    """Whether the mora at ``index`` only lengthens the vowel before it (ー, かあ, こう, けい)."""
    if index == 0 or morae[index - 1] in (SOKUON, HATSUON):
        return False
    if morae[index] == CHOON:
        return True
    previous = _vowel_before(morae, index)
    vowel = _VOWEL_KANA.get(morae[index])
    if previous is None or vowel is None or morae[index - 1] == CHOON:
        return False
    return vowel == previous or (previous, vowel) in (("o", "u"), ("e", "i"))

def _long_mark(vowel: str, katakana: bool) -> str:
    return CHOON if katakana else _LONG_KANA[vowel]

def _edits(morae: list[str], katakana: bool) -> list[tuple[str, list[str]]]:
    """Every one-step misspelling of a word, labelled with the kind of mistake."""
    table = _KATAKANA_MORAE if katakana else _HIRAGANA_MORAE
    edits: list[tuple[str, list[str]]] = []

    def replaced(index: int, *new: str) -> list[str]:
        return [*morae[:index], *new, *morae[index + 1 :]]

    def inserted(index: int, new: str) -> list[str]:
        return [*morae[:index], new, *morae[index:]]

    for i, mora in enumerate(morae):
        phones = _phones(mora)
        if _lengthens(morae, i):
            # A long vowel heard short, as ん, as っ, or moved:
            # びょうき -> びょき, タクシー -> タークシ.
            edits.append(("special", replaced(i)))
            edits.append(("special", replaced(i, HATSUON)))
            if i + 1 < len(morae):
                edits.append(("special", replaced(i, SOKUON)))
            if katakana and mora == CHOON:
                without = replaced(i)
                for j in range(1, len(without) + 1):
                    if j != i:
                        edits.append(("special", [*without[:j], CHOON, *without[j:]]))
            continue
        if mora == SOKUON or mora == HATSUON:
            vowel = _vowel_before(morae, i)
            other = HATSUON if mora == SOKUON else SOKUON
            edits.append(("special", replaced(i)))
            edits.append(("special", replaced(i, other)))
            if vowel is not None:
                edits.append(("special", replaced(i, _long_mark(vowel, katakana))))
            edits.append(("special", replaced(i, "つ")))
            if mora == HATSUON:
                edits.append(("special", replaced(i, "く")))
            continue
        if phones is None:
            continue
        consonant, vowel = phones
        nxt = morae[i + 1] if i + 1 < len(morae) else None
        # Before a long mark, another vowel would change what the mark means (きょう -> きゃう).
        lengthened = nxt is not None and _lengthens(morae, i + 1)
        if lengthened:
            pass
        elif len(mora) == 1:
            for mate in _ROW_OF.get(mora, ""):
                if mate != mora:
                    edits.append(("vowel", replaced(i, mate)))
        else:
            for other in VOWELS:
                if other != vowel and (consonant, other) in table:
                    edits.append(("vowel", replaced(i, table[(consonant, other)])))
        for other in _NEIGHBOURS.get(consonant, ()):
            if (other, vowel) in table:
                edits.append(("consonant", replaced(i, table[(other, vowel)])))
        if len(mora) == 2 and mora[1] in "ゃゅょ":
            # びょ -> びよ (full-size glide), しゅ -> す, きゃ -> き.
            edits.append(("youon", replaced(i, mora[0], chr(ord(mora[1]) + 1))))
            plain = _UNGLIDE.get(consonant)
            if plain is not None and (plain, vowel) in table:
                edits.append(("youon", replaced(i, table[(plain, vowel)])))
            if not lengthened:
                edits.append(("youon", replaced(i, mora[0])))
        if not lengthened and nxt not in (SOKUON, HATSUON):
            edits.append(("insert", inserted(i + 1, _long_mark(vowel, katakana))))
        if nxt is not None and nxt not in _SPECIAL:
            edits.append(("insert", inserted(i + 1, SOKUON)))
            edits.append(("insert", inserted(i + 1, HATSUON)))
    return edits

def is_well_formed(morae: list[str], katakana: bool) -> bool:
    """Whether a spelling is something a learner could plausibly see written."""
    if not morae or morae[0] in _SPECIAL or morae[-1] == SOKUON:
        return False
    geminate = _GEMINATE_KATAKANA if katakana else _GEMINATE
    for i, mora in enumerate(morae):
        if mora[0] in _SMALL or set(mora) & EXCLUDED_KANA:
            return False
        if mora == SOKUON:
            phones = _phones(morae[i + 1])
            if phones is None or not phones[0].startswith(geminate):
                return False
        if mora == HATSUON and i + 1 < len(morae):
            phones = _phones(morae[i + 1])
            # ん before a bare vowel or y/w reads oddly (きんえん) and is easy to mishear.
            if phones is None or phones[0] in ("", "y", "w"):
                return False
        if mora == CHOON and (not katakana or morae[i - 1] in _SPECIAL):
            return False
        if i >= 2 and _lengthens(morae, i) and _lengthens(morae, i - 1):
            return False
    try:
        to_romaji("".join(morae))
    except UnsupportedReadingError:
        return False
    return True

def _render(morae: list[str], katakana: bool) -> str:
    text = "".join(morae)
    return to_katakana(text) if katakana else text

def _pick(
    by_kind: dict[str, list[str]], seen: set[str], chosen: list[str], count: int,
    rng: random.Random,
) -> None:
    """Draw options by weighted mistake kind, at most two of a kind, skipping sound-alikes."""
    used = {kind: 0 for kind in by_kind}
    for options in by_kind.values():
        rng.shuffle(options)
    while len(chosen) < count:
        kinds = [
            kind for kind, options in by_kind.items() if options and used[kind] < _MAX_PER_KIND
        ]
        if not kinds:
            return
        kind = rng.choices(kinds, weights=[_KIND_WEIGHTS[k] for k in kinds])[0]
        text = by_kind[kind].pop()
        key = sound_key(text)
        if key not in seen:
            seen.add(key)
            chosen.append(text)
            used[kind] += 1

def _candidates(edits: list[tuple[str, list[str]]], katakana: bool) -> dict[str, list[str]]:
    by_kind: dict[str, list[str]] = {}
    for kind, edited in edits:
        if is_well_formed(edited, katakana):
            text = _render(edited, katakana)
            options = by_kind.setdefault(kind, [])
            if text not in options:
                options.append(text)
    return by_kind

def word_distractors(answer: str, rng: random.Random, count: int = 3) -> list[str]:
    """Up to ``count`` misspellings of a word, each sounding different from the others.

    One-step changes come first; two-step changes fill the gap only for short words with
    too few one-step options. Callers must check that enough options came back.
    """
    katakana = is_katakana(answer)
    morae = split_morae(answer)
    seen = {sound_key(answer)}
    chosen: list[str] = []
    first = _edits(morae, katakana)
    _pick(_candidates(first, katakana), seen, chosen, count, rng)
    if len(chosen) < count:
        second = [
            (kind, edited2)
            for _, edited in first
            if is_well_formed(edited, katakana)
            for kind, edited2 in _edits(edited, katakana)
        ]
        _pick(_candidates(second, katakana), seen, chosen, count, rng)
    return chosen

def _shape_mates(char: str) -> set[str]:
    groups = KATAKANA_SHAPES if is_katakana(char) else HIRAGANA_SHAPES
    return {mate for group in groups if char in group for mate in group if mate != char}

def char_distractors(
    answer: str, pool: Iterable[str], rng: random.Random, count: int = 3
) -> list[str]:
    """``count`` other kana from ``pool`` that look or sound like ``answer``.

    Look-alikes come first (ら/ろ/う/る), then sound neighbours with the same consonant or
    a confusable consonant and the same vowel (ざ/ぜ/ぎ), then the rest of the pool.
    """
    katakana = is_katakana(answer)
    phones = _phones(to_hiragana(answer))
    shapes = _shape_mates(answer)
    look: list[str] = []
    sound: list[str] = []
    rest: list[str] = []
    for kana in dict.fromkeys(pool):
        if (
            kana == answer
            or is_katakana(kana) != katakana
            or set(to_hiragana(kana)) & EXCLUDED_KANA
        ):
            continue
        other = _phones(to_hiragana(kana))
        if kana in shapes:
            look.append(kana)
        elif phones and other and (
            other[0] == phones[0]
            or (other[1] == phones[1] and other[0] in _NEIGHBOURS.get(phones[0], ()))
        ):
            sound.append(kana)
        else:
            rest.append(kana)
    for group in (look, sound, rest):
        rng.shuffle(group)
    seen = {sound_key(answer)}
    chosen: list[str] = []
    for kana in [*look, *sound, *rest]:
        key = sound_key(kana)
        if key not in seen:
            seen.add(key)
            chosen.append(kana)
            if len(chosen) == count:
                break
    return chosen

def shuffled_options(
    answer: str, distractors: list[str], rng: random.Random
) -> tuple[list[str], int]:
    """The answer and its distractors in random order, with the answer's index."""
    options = [answer, *distractors]
    rng.shuffle(options)
    return options, options.index(answer)
