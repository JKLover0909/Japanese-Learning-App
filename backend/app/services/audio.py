"""Pre-recorded audio clips for listening questions.

``scripts/generate_audio.py`` records clips into ``frontend/public/assets/audio/`` and
writes ``app/content/audio.json``: ``{"credit": ..., "clips": {prompt: file name}}``.
The SPA build copies the clips into ``dist/assets/audio/``, where the app serves them
with a long cache lifetime (file names are content hashes).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parents[1] / "content" / "audio.json"
AUDIO_URL_PREFIX = "/assets/audio/"

@dataclass(frozen=True)
class AudioLibrary:
    credit: str = ""
    clips: dict[str, str] = field(default_factory=dict)

    def has(self, prompt: str) -> bool:
        return prompt in self.clips

    def url(self, prompt: str) -> str | None:
        name = self.clips.get(prompt)
        return f"{AUDIO_URL_PREFIX}{name}" if name else None

def load_audio_library(path: Path = MANIFEST_PATH) -> AudioLibrary:
    """Read the clip manifest; a missing file means no chapter test can be generated."""
    if not path.is_file():
        return AudioLibrary()
    data = json.loads(path.read_text(encoding="utf-8"))
    return AudioLibrary(credit=str(data.get("credit", "")), clips=dict(data.get("clips", {})))
