#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Iterable


TITLE_SUFFIX_RE = re.compile(
    r"""
    \s*
    (?:
        \[[^\]]*(?:\d{3,4}p|av1|x264|x265|h264|h265|\d{4})[^\]]*\]
        |
        \([^\)]*(?:\d{3,4}p|av1|x264|x265|h264|h265|\d{4})[^\)]*\)
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

LEADING_SITE_RE = re.compile(r"^\s*(?:\[[^\]]+\]\s*[-:]?\s*)+")
LEADING_DATE_RE = re.compile(r"^\s*\d{4}-\d{2}-\d{2}\s*-\s*")
TRAILING_RESOLUTION_RE = re.compile(
    r"""
    \s*
    (?:
        \(\d{4}(?:[-./]\d{2}(?:[-./]\d{2})?)?\)
    )?
    \s*
    (?:
        \d{3,4}p
        |
        [xh]26[45]
        |
        h26[45]
        |
        av1
        |
        4k
        |
        xxx
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
TRAILING_YEAR_RE = re.compile(r"\s*\(\d{4}\)\s*$")
LEADING_SHORT_DATE_RE = re.compile(r"^\s*\d{2}[.-]\d{2}[.-]\d{2}\s+")
LEADING_SITE_SHORT_DATE_RE = re.compile(r"^\s*\[[^\]]+\]\s+\d{2}[.-]\d{2}[.-]\d{2}\s+")
SPACE_RE = re.compile(r"\s+")
SEPARATOR_RE = re.compile(r"\s*(?:,| and | & |/)\s*", re.IGNORECASE)
NOISE_RE = re.compile(
    r"\b(?:orgy|scene|episode|compilation|collection|files?|video|full)\b",
    re.IGNORECASE,
)
DESCRIPTION_START_RE = re.compile(
    r"^(?:sucking|fucking|playing|cheating|i\s|my\s|please\s|step\s)",
    re.IGNORECASE,
)
SITE_DATE_PERFORMER_STOP_RE = re.compile(
    r"\b(?:double|netflix|he|she|i|my|the|a|an|little|morning|cute|petite|step|cinderella|missionary|bathroom|teen|hardcore|cum|cumming|sucking|fucking)\b",
    re.IGNORECASE,
)


def load_titles(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    titles = load_titles_from_json(text)
    if titles:
        return titles

    titles = load_titles_from_html(text)
    if titles:
        return titles

    return [clean_whitespace(html.unescape(line)) for line in text.splitlines() if line.strip()]


def load_titles_from_json(text: str) -> list[str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []

    titles: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            name = node.get("name")
            if isinstance(name, str) and name.strip():
                titles.append(name.strip())

            attrs = node.get("attributes")
            if isinstance(attrs, dict):
                attr_name = attrs.get("name")
                if isinstance(attr_name, str) and attr_name.strip():
                    titles.append(attr_name.strip())

            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return dedupe_preserve_order(titles)


def load_titles_from_html(text: str) -> list[str]:
    matches = re.findall(r">([^<]{4,})<", text)
    cleaned = [clean_whitespace(html.unescape(match)) for match in matches]
    candidates = []
    for item in cleaned:
        if len(item) < 8:
            continue
        if "Redirecting to" in item:
            continue
        if item.lower() in {"torrents list", "download"}:
            continue
        if "[" in item or " - " in item or ", " in item:
            candidates.append(item)
    return dedupe_preserve_order(candidates)


def clean_whitespace(value: str) -> str:
    return SPACE_RE.sub(" ", value).strip()


def strip_title_noise(title: str) -> str:
    value = clean_whitespace(title)
    value = LEADING_SITE_RE.sub("", value)
    value = LEADING_SHORT_DATE_RE.sub("", value)

    while True:
        updated = TITLE_SUFFIX_RE.sub("", value)
        if updated == value:
            break
        value = updated

    while True:
        updated = TRAILING_RESOLUTION_RE.sub("", value)
        if updated == value:
            break
        value = updated

    value = TRAILING_YEAR_RE.sub("", value)

    return clean_whitespace(value)


def split_performer_block(title: str) -> str:
    site_date_match = LEADING_SITE_SHORT_DATE_RE.match(title)
    if site_date_match:
        tail = strip_title_noise(title[site_date_match.end() :])
        words = tail.split()
        performer_words: list[str] = []
        for word in words:
            if SITE_DATE_PERFORMER_STOP_RE.match(word):
                break
            performer_words.append(word)
            if len(performer_words) == 2:
                break
        if len(performer_words) >= 2:
            return " ".join(performer_words)

    value = strip_title_noise(title)
    value = LEADING_DATE_RE.sub("", value)

    if " - " in value:
        return value.split(" - ", 1)[0].strip()

    if ", " in value:
        left, right = value.split(", ", 1)
        # Prefer the comma split when the right side looks like a scene title.
        if right and right[:1].islower():
            return left.strip()
        if NOISE_RE.search(right):
            return left.strip()

    return value


def looks_like_performer(candidate: str) -> bool:
    value = candidate.strip(" -_,./")
    if not value:
        return False
    if len(value) < 2:
        return False
    if NOISE_RE.search(value):
        return False
    if DESCRIPTION_START_RE.search(value):
        return False
    if re.search(r"\d{3,4}p|x26[45]|h26[45]|av1", value, re.IGNORECASE):
        return False
    if re.match(r"^\d{2}[.-]\d{2}[.-]\d{2}\b", value):
        return False
    return True


def extract_performers(title: str) -> list[str]:
    performer_block = split_performer_block(title)
    parts = [clean_whitespace(part) for part in SEPARATOR_RE.split(performer_block)]
    performers = [part for part in parts if looks_like_performer(part)]
    return dedupe_preserve_order(performers)


def slugify(name: str) -> str:
    value = name.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "unknown"


def dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract candidate performer names from BitPorn bookmark exports."
    )
    parser.add_argument("input", type=Path, help="Path to JSON, HTML, or plain-text input")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a text report",
    )
    args = parser.parse_args()

    titles = load_titles(args.input)
    candidates: list[dict[str, object]] = []
    all_performers: list[str] = []

    for title in titles:
        performers = extract_performers(title)
        if not performers:
            continue
        all_performers.extend(performers)
        candidates.append(
            {
                "title": title,
                "performers": performers,
            }
        )

    unique_performers = dedupe_preserve_order(all_performers)
    review = [
        {
            "performer": performer,
            "slug": slugify(performer),
        }
        for performer in unique_performers
    ]

    if args.json:
        json.dump(
            {
                "titles_seen": len(titles),
                "titles_matched": len(candidates),
                "performers": review,
                "matches": candidates,
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0

    print(f"Titles seen: {len(titles)}")
    print(f"Titles with candidate performers: {len(candidates)}")
    print(f"Unique performers: {len(review)}")
    print("")
    for item in review:
        print(f"{item['performer']} -> {item['slug']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
