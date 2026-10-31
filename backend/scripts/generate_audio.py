"""Record the audio clips used by chapter listening tests with a local VOICEVOX engine.

Usage (from ``backend/``, with VOICEVOX running on port 50021)::

    docker run --rm -d --name jp-voicevox -p 127.0.0.1:50021:50021 \\
        voicevox/voicevox_engine:cpu-ubuntu22.04-0.25.2
    .venv/bin/python scripts/generate_audio.py
    docker stop jp-voicevox
    .venv/bin/python scripts/generate_audio.py --check   # no engine needed

Clips go to ``frontend/public/assets/audio/<content hash>.mp3`` and the prompt -> file map
to ``app/content/audio.json``. Existing clips recorded with the same voice settings are
kept, so a re-run only records new prompts. Every clip is checked against what VOICEVOX
says it pronounced; a mismatch (for example は read as the particle "wa") is recorded
again in kana mode, and the script fails if it is still wrong.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import REPO_ROOT  # noqa: E402
from app.content.validation import LESSONS_DIR, load_lessons  # noqa: E402
from app.services.audio import MANIFEST_PATH  # noqa: E402
from app.services.chapter_test import Candidate, audio_candidates  # noqa: E402
from app.services.listening import CHOON, sound_key, split_morae, to_katakana  # noqa: E402

AUDIO_DIR = REPO_ROOT / "frontend" / "public" / "assets" / "audio"
SPEAKER = 2
CREDIT = "VOICEVOX:四国めたん"
# Slightly slow and padded, so a learner hears the start and end of each word clearly.
SETTINGS = {
    "speedScale": 0.9,
    "prePhonemeLength": 0.15,
    "postPhonemeLength": 0.3,
    "outputSamplingRate": 24000,
    "bitrate": "48k",
}
_VOWEL_KATAKANA = {"a": "ア", "i": "イ", "u": "ウ", "e": "エ", "o": "オ"}

class Engine:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")

    def _post(self, path: str, params: dict[str, object], body: object | None = None) -> bytes:
        query = urllib.parse.urlencode(params)
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"{self.url}{path}?{query}", data=data or b"", method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()

    def version(self) -> str:
        with urllib.request.urlopen(f"{self.url}/version", timeout=10) as response:
            return json.loads(response.read())

    def text_query(self, text: str) -> dict:
        return json.loads(self._post("/audio_query", {"text": text, "speaker": SPEAKER}))

    def kana_query(self, kana: str) -> dict:
        """A query from AquesTalk-style kana, which reads は/へ as ha/he rather than particles."""
        phrases = json.loads(
            self._post("/accent_phrases", {"text": kana, "speaker": SPEAKER, "is_kana": "true"})
        )
        query = self.text_query("あ")
        query["accent_phrases"] = phrases
        return query

    def synthesize(self, query: dict) -> bytes:
        query = dict(query)
        for key in ("speedScale", "prePhonemeLength", "postPhonemeLength", "outputSamplingRate"):
            query[key] = SETTINGS[key]
        return self._post("/synthesis", {"speaker": SPEAKER}, query)

def heard(query: dict) -> str:
    """What VOICEVOX will say, in the same form as ``sound_key``."""
    parts: list[str] = []
    for phrase in query["accent_phrases"]:
        for mora in phrase["moras"]:
            vowel = mora["vowel"]
            if vowel == "N":
                parts.append("n")
            elif vowel == "cl":
                parts.append("")
            else:
                parts.append((mora["consonant"] or "").lower() + vowel.lower())
    for i, part in enumerate(parts):
        if part == "" and i + 1 < len(parts):
            parts[i] = "t" if parts[i + 1].startswith("ch") else parts[i + 1][:1]
    return "".join(parts).replace("ou", "oo").replace("ei", "ee")

def expected(prompt: str) -> str:
    return sound_key(prompt).replace("'", "")

def kana_notation(prompt: str, text_query: dict) -> str:
    """Katakana with accent marks; reuses the accent VOICEVOX chose when the morae line up."""
    morae: list[str] = []
    for mora in split_morae(prompt):
        if mora == CHOON:
            # Kana mode does not accept ー; spell the long vowel out as VOICEVOX itself does.
            vowel = expected("".join(morae))[-1:] or "a"
            morae.append(_VOWEL_KATAKANA.get(vowel, "ア"))
        else:
            morae.append(to_katakana(mora))
    sizes = [len(phrase["moras"]) for phrase in text_query["accent_phrases"]]
    if sum(sizes) != len(morae):
        sizes, accents = [len(morae)], [1]
    else:
        accents = [phrase["accent"] for phrase in text_query["accent_phrases"]]
    phrases: list[str] = []
    start = 0
    for size, accent in zip(sizes, accents, strict=True):
        chunk = morae[start : start + size]
        chunk[accent - 1] += "'"
        phrases.append("".join(chunk))
        start += size
    return "/".join(phrases)

def record(engine: Engine, candidate: Candidate) -> tuple[bytes, str]:
    """MP3 bytes for a prompt, and how it was made ("text" or "kana")."""
    prompt = candidate.prompt
    target = expected(prompt)
    text_query = engine.text_query(prompt)
    if candidate.kind == "char" or heard(text_query) != target:
        query, mode = engine.kana_query(kana_notation(prompt, text_query)), "kana"
    else:
        query, mode = text_query, "text"
    if heard(query) != target:
        raise RuntimeError(f"{prompt}: VOICEVOX reads {heard(query)!r}, expected {target!r}")
    wav = engine.synthesize(query)
    mp3 = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-ac", "1",
            "-ar", str(SETTINGS["outputSamplingRate"]), "-codec:a", "libmp3lame",
            "-b:a", str(SETTINGS["bitrate"]), "-map_metadata", "-1", "-f", "mp3", "pipe:1",
        ],
        input=wav, capture_output=True, check=True,
    ).stdout
    return mp3, mode

def load_manifest() -> dict:
    if MANIFEST_PATH.is_file():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}

def needed_prompts(lessons_dir: Path) -> list[Candidate]:
    candidates = [
        Candidate(item_id=0, lesson_slug=lesson.slug, prompt=item.prompt, kind=item.kind)
        for lesson in load_lessons(lessons_dir)
        for item in lesson.items
    ]
    return sorted(audio_candidates(candidates), key=lambda candidate: candidate.prompt)

def check(candidates: list[Candidate]) -> int:
    clips = load_manifest().get("clips", {})
    problems = [f"no clip for {c.prompt}" for c in candidates if c.prompt not in clips]
    problems += [
        f"missing file {name} for {prompt}"
        for prompt, name in clips.items()
        if not (AUDIO_DIR / name).is_file()
    ]
    for problem in problems:
        print(f"FAIL {problem}")
    print(f"{'FAIL' if problems else 'OK  '} {len(clips)} clips for {len(candidates)} prompts")
    return 1 if problems else 0

def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--engine", default="http://127.0.0.1:50021")
    parser.add_argument("--lessons", type=Path, default=LESSONS_DIR)
    parser.add_argument("--check", action="store_true", help="only verify the manifest and files")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    candidates = needed_prompts(args.lessons)
    if args.check:
        return check(candidates)

    engine = Engine(args.engine)
    version = engine.version()
    old = load_manifest()
    same_voice = old.get("speaker") == SPEAKER and old.get("settings") == SETTINGS
    old_clips: dict[str, str] = old.get("clips", {}) if same_voice else {}
    clips = {
        c.prompt: old_clips[c.prompt]
        for c in candidates
        if c.prompt in old_clips and (AUDIO_DIR / old_clips[c.prompt]).is_file()
    }
    todo = [c for c in candidates if c.prompt not in clips]
    print(f"VOICEVOX {version}: {len(clips)} clips kept, {len(todo)} to record")
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    modes = {"text": 0, "kana": 0}

    def work(candidate: Candidate) -> None:
        try:
            mp3, mode = record(engine, candidate)
        except Exception as exc:  # noqa: BLE001 - report every failure, then exit non-zero
            failures.append(f"{candidate.prompt}: {exc}")
            return
        name = hashlib.sha256(mp3).hexdigest()[:20] + ".mp3"
        (AUDIO_DIR / name).write_bytes(mp3)
        clips[candidate.prompt] = name
        modes[mode] += 1
        done = sum(modes.values())
        if done % 50 == 0:
            print(f"  {done}/{len(todo)}", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(work, todo))

    manifest = {
        "version": 1,
        "credit": CREDIT,
        "engine": f"VOICEVOX {version}",
        "speaker": SPEAKER,
        "settings": SETTINGS,
        "clips": dict(sorted(clips.items())),
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    kept = set(clips.values())
    removed = [path for path in AUDIO_DIR.glob("*.mp3") if path.name not in kept]
    for path in removed:
        path.unlink()
    print(
        f"recorded {modes['text']} in text mode, {modes['kana']} in kana mode; "
        f"removed {len(removed)} unused"
    )
    for failure in failures:
        print(f"FAIL {failure}")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
