"""Validate lesson content files and print a short summary.

Usage (from ``backend/``)::

    .venv/bin/python scripts/validate_content.py [LESSONS_DIR] [--only SLUG]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402

from app.content.schema import LessonFile  # noqa: E402
from app.content.validation import LESSONS_DIR, validate_lesson  # noqa: E402
from app.services.romaji import romaji_options  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=LESSONS_DIR)
    parser.add_argument("--only", help="validate a single lesson slug")
    parser.add_argument("--show", action="store_true", help="print every item with its romaji")
    args = parser.parse_args()

    failed = False
    for path in sorted(args.directory.glob("*.json")):
        # Files are named "<NN>-<slug>.json"; skip others early so a half-written
        # file for a different lesson does not fail a targeted check.
        if args.only and path.stem.split("-", 1)[-1] != args.only:
            continue
        try:
            lesson = LessonFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValidationError) as exc:
            print(f"FAIL {path.name}: {exc}")
            failed = True
            continue
        problems = validate_lesson(lesson)
        kinds = Counter(item.kind for item in lesson.items)
        status = "FAIL" if problems else "OK  "
        print(f"{status} {path.name}: {len(lesson.items)} items {dict(kinds)}")
        for problem in problems:
            print(f"     - {problem}")
        if args.show:
            for item in lesson.items:
                romaji = " / ".join(romaji_options(item.readings))
                print(f"     {item.key:<28} {item.prompt:<14} {romaji}")
        failed |= bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
