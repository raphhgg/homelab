#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".m4v",
    ".ts",
    ".webm",
    ".flv",
}
BRACKETED_RE = re.compile(r"[\[\(][^\]\)]*[\]\)]")
DATE_RE = re.compile(r"\b\d{4}[.\-_]\d{2}[.\-_]\d{2}\b|\b\d{2}[.\-_]\d{2}[.\-_]\d{2}\b")
TOKEN_RE = re.compile(r"[^a-z0-9]+")
SPACE_RE = re.compile(r"\s+")
RESOLUTION_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"\b(?:2160p|4k|uhd)\b", re.IGNORECASE), 2160),
    (re.compile(r"\b1440p\b", re.IGNORECASE), 1440),
    (re.compile(r"\b(?:1080p|fullhd|fhd)\b", re.IGNORECASE), 1080),
    (re.compile(r"\b756p\b", re.IGNORECASE), 756),
    (re.compile(r"\b720p\b", re.IGNORECASE), 720),
    (re.compile(r"\b540p\b", re.IGNORECASE), 540),
    (re.compile(r"\b480p\b", re.IGNORECASE), 480),
    (re.compile(r"\b360p\b", re.IGNORECASE), 360),
]
NOISE_WORDS = {
    "onlyfans",
    "of",
    "pornhub",
    "hegre",
    "com",
    "fansdb",
    "xxx",
    "rq",
    "ppv",
    "mp4",
    "mkv",
    "mov",
    "avi",
    "wmv",
    "webm",
    "flv",
    "x264",
    "x265",
    "h264",
    "h265",
    "hevc",
    "av1",
    "2160p",
    "1440p",
    "1080p",
    "756p",
    "720p",
    "540p",
    "480p",
    "360p",
    "4k",
    "uhd",
    "fullhd",
    "fhd",
}


@dataclass
class Candidate:
    path: Path
    relative_path: str
    title: str
    normalized_title: str
    resolution: int
    size: int


def build_performer_words(performer: str | None) -> set[str]:
    if not performer:
        return set()
    return {word for word in TOKEN_RE.split(performer.lower()) if word}


def resolution_rank(title: str) -> int:
    for pattern, score in RESOLUTION_PATTERNS:
        if pattern.search(title):
            return score
    return 0


def cleaned_title_words(title: str, performer: str | None = None, strip_dates: bool = True) -> list[str]:
    value = BRACKETED_RE.sub(" ", title)
    if strip_dates:
        value = DATE_RE.sub(" ", value)
    value = value.replace("&", " and ")
    value = TOKEN_RE.sub(" ", value.lower())
    words = [word for word in SPACE_RE.split(value.strip()) if word]
    performer_words = build_performer_words(performer)

    cleaned: list[str] = []
    for word in words:
        if len(word) == 1 and not word.isdigit():
            continue
        if word in performer_words:
            continue
        if word in NOISE_WORDS:
            continue
        if word.isdigit() and len(word) == 4:
            continue
        cleaned.append(word)

    return cleaned


def normalize_title(title: str, performer: str | None = None) -> str:
    return " ".join(cleaned_title_words(title, performer, strip_dates=True)).strip()


def dedupe_key(title: str, performer: str | None = None) -> str:
    normalized = normalize_title(title, performer)
    if len(normalized.split()) >= 2:
        return normalized

    # Site/date-only releases can normalize down to just the site name, which is
    # too broad and can merge unrelated scenes. Preserve dates for weak keys.
    dated = " ".join(cleaned_title_words(title, performer, strip_dates=False)).strip()
    if len(dated.split()) >= 2:
        return dated

    return normalized or title.casefold().strip()


def iter_video_candidates(root: Path, performer: str) -> list[Candidate]:
    candidates: list[Candidate] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        relative_path = path.relative_to(root).as_posix()
        title = path.stem
        candidates.append(
            Candidate(
                path=path,
                relative_path=relative_path,
                title=title,
                normalized_title=normalize_title(title, performer),
                resolution=resolution_rank(title),
                size=path.stat().st_size,
            )
        )
    return candidates


def candidate_sort_key(candidate: Candidate) -> tuple[int, int, int, str]:
    # Prefer the highest resolution, then largest file, then the shortest path.
    return (
        candidate.resolution,
        candidate.size,
        -len(candidate.relative_path),
        candidate.relative_path.casefold(),
    )


def dedupe(root: Path, performer: str) -> tuple[int, int]:
    groups: dict[str, list[Candidate]] = {}
    for candidate in iter_video_candidates(root, performer):
        key = dedupe_key(candidate.title, performer)
        groups.setdefault(key, []).append(candidate)

    kept = 0
    removed = 0
    for grouped in groups.values():
        if len(grouped) == 1:
            kept += 1
            continue

        grouped_sorted = sorted(grouped, key=candidate_sort_key, reverse=True)
        best = grouped_sorted[0]
        kept += 1
        for candidate in grouped_sorted[1:]:
            if candidate.path == best.path:
                continue
            candidate.path.unlink(missing_ok=True)
            removed += 1
            print(f"removed: {candidate.path}")

    return kept, removed


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: dedupe-nsfw-media.py <media_root> <performer>", file=sys.stderr)
        return 1

    root = Path(sys.argv[1])
    performer = sys.argv[2]
    if not root.is_dir():
        print(f"skip: media root missing: {root}")
        return 0

    kept, removed = dedupe(root, performer)
    print(f"summary: kept={kept} removed={removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
