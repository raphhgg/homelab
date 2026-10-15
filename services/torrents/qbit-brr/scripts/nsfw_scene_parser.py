#!/usr/bin/env python3

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
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

LOWER_WORDS = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "vs"}
STRIP_WORDS = {
    "onlyfans",
    "fansly",
    "fanvue",
    "hegre",
    "hegrecom",
    "momsfamilysecrets",
    "source",
    "xxx",
    "wrb",
    "p1a",
    "rq",
    "ppv",
    "mp4",
    "mkv",
    "wmv",
    "webm",
    "flv",
    "hevc",
    "x264",
    "x265",
    "h264",
    "h265",
    "aac",
    "ddp",
    "2160p",
    "1080p",
    "720p",
    "480p",
    "4k",
    "8k",
    "uhd",
    "fullhd",
    "ultrahd",
}
NOISY_TITLE_WORDS = {
    "fansdb",
    "source",
    "compilation",
    "onlyfans",
    "hegre",
    "chaturbate",
    "tomboyz",
    "atkgalleria",
    "stepsiblingscaught",
    "brattysis",
    "exxxtrasmall",
    "shesbreedingmaterial",
    "deanralphs",
    "sel018atk",
}
NOISY_FOLDER_PARTS = {
    "videos",
    "video",
    "packs",
    "pack",
    "of-a-part3",
    "of-a-part2",
    "of-a-part1",
    "arianamarie",
}


@dataclass(frozen=True)
class ParsedSceneMetadata:
    title: str
    date: str
    confidence: str
    rename_safe: bool
    family: str


def cleanup_filename_component(value: str) -> str:
    cleaned = value
    replacements = [
        (r"[_\.]+", " "),
        (r"\[[^\]]+\]", " "),
        (r"\((?:24fps|smoother|cum on breasts|p\d+[a-z]?|1080p|2160p|4k|sep \d{1,2}, \d{4})[^)]*\)", " "),
        (r"\b(part\s*\d+|pack by [^-]+|fullhd|ultrahd)\b", " "),
        (r"\b(data|torrents|nsfw|media)\b", " "),
        (r"\b\d{3,4}fps\b", " "),
        (r"\b\d+x-rife[\w.-]*\b", " "),
        (r"\b\d{3,4}p\b", " "),
        (r"\b(2160p|1080p|720p|480p|4k|8k|x264|x265|h264|h265|hevc|aac|ddp5?\.?1?|wmv|mp4|mkv|webm|flv)\b", " "),
    ]
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bthe making the\b", "the making of the", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    cleaned = re.sub(r"(?:,\s*){2,}", ", ", cleaned)
    cleaned = re.sub(r"\s+-\s+", " - ", cleaned)
    cleaned = re.sub(r"\[\s*\]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -._,")
    return cleaned


def titlecase_loose_text(value: str) -> str:
    words = []
    for word in value.split():
        if word.isupper() and len(word) <= 4:
            words.append(word)
        elif re.fullmatch(r"[A-Za-z]\d+", word):
            words.append(word.upper())
        else:
            words.append(word.capitalize())
    result = " ".join(words)
    for lower in LOWER_WORDS:
        result = re.sub(rf"\b{lower.capitalize()}\b", lower, result)
    if result:
        result = result[0].upper() + result[1:]
    return result


def is_weak_title(title: str) -> bool:
    normalized = title.strip().casefold()
    if not normalized:
        return True
    if normalized in {"data", "video", "scene", "source"}:
        return True
    if re.fullmatch(r"\d+( \d+)*", normalized):
        return True
    if not re.search(r"[a-z]", normalized):
        return True
    if re.fullmatch(r"[,#\s]+", normalized):
        return True
    if normalized.count(",") >= 2 and len(re.sub(r"[^a-z]", "", normalized)) < 8:
        return True
    if "the making the" in normalized:
        return True
    if " chaturbate " in f" {normalized} " and re.fullmatch(r".*chaturbate \d+.*", normalized):
        return True
    return False


def has_noisy_title_markers(title: str) -> bool:
    normalized = title.casefold()
    if any(word in normalized for word in NOISY_TITLE_WORDS):
        return True
    if re.search(r"\b\d{3,4}p\b", normalized):
        return True
    if re.search(r"\((20\d{2})\)", normalized):
        return True
    if re.search(r"\b[0-9a-f]{10,}\b", normalized):
        return True
    if re.search(r"\b[a-z]{2,}\d{3,}[a-z0-9]*\b", normalized):
        return True
    if re.search(r"\b\d{6,}\b", normalized):
        return True
    if re.search(r"\bhd\b", normalized) and len(normalized.split()) <= 3:
        return True
    return False


def looks_like_clean_scene_title(title: str) -> bool:
    return bool(title) and not is_weak_title(title) and not has_noisy_title_markers(title)


def strip_performer_name(value: str, performer_name: str) -> str:
    escaped = re.escape(performer_name)
    cleaned = value
    for pattern in (
        rf"^{escaped}\s*-\s*",
        rf"^{escaped}\s+",
        rf"^{escaped}$",
        rf"\b{escaped}\b",
    ):
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" -")


def date_from_match(match: re.Match[str]) -> str:
    return iso_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def short_date_to_iso(match: re.Match[str]) -> str:
    yy = int(match.group(1))
    return iso_date(2000 + yy, int(match.group(2)), int(match.group(3)))


def iso_date(year: int, month: int, day: int) -> str:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def folder_candidates(path: Path, performer_name: str) -> list[str]:
    ignored = {"", "/", "data", "torrents", "nsfw", "media", performer_name.casefold()}
    candidates: list[str] = []
    for folder in reversed(path.parents):
        name = folder.name.strip()
        if not name or name.casefold() in ignored:
            continue
        if name.casefold() in NOISY_FOLDER_PARTS:
            continue
        if re.fullmatch(r"of-a-part\d+", name, flags=re.IGNORECASE):
            continue
        cleaned = cleanup_filename_component(strip_performer_name(name, performer_name))
        if cleaned and looks_like_clean_scene_title(cleaned):
            candidates.append(cleaned)
    return candidates


def detect_date(stem: str) -> tuple[str, str]:
    year_match = re.search(r"(20\d{2})[-_. ]?(\d{2})[-_. ]?(\d{2})", stem)
    if year_match:
        return date_from_match(year_match), stem.replace(year_match.group(0), " ")
    short_match = re.search(r"\b(\d{2})[._-](\d{2})[._-](\d{2})\b", stem)
    if short_match:
        return short_date_to_iso(short_match), stem.replace(short_match.group(0), " ")
    return "", stem


def pack_like(path: Path) -> bool:
    haystack = " / ".join(part.casefold() for part in path.parts)
    return " pack " in f" {haystack} " or "pack by" in haystack


def parse_hegre(path: Path, performer_name: str) -> ParsedSceneMetadata | None:
    stem = path.stem
    for pattern in (
        rf"(?:\[hegre\.com\]|hegre)\s*(20\d{{2}})[.\-_](\d{{2}})[.\-_](\d{{2}})\s*-\s*(.*?)\s*-\s*{re.escape(performer_name)}(?:\s+\w+)?$",
        rf"(?:\[hegre\.com\]|hegre)\s*(20\d{{2}})[.\-_](\d{{2}})[.\-_](\d{{2}})\s+{re.escape(performer_name)}(?:\s+\w+)?\s*-\s*(.*?)$",
    ):
        match = re.search(pattern, stem, flags=re.IGNORECASE)
        if match:
            title = titlecase_loose_text(cleanup_filename_component(match.group(4)))
            if is_weak_title(title):
                return None
            title = re.sub(r"^Hegre\s+", "", title, flags=re.IGNORECASE)
            title = re.sub(r"^(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+-\s+", "", title)
            return ParsedSceneMetadata(title=title, date=date_from_match(match), confidence="high", rename_safe=True, family="hegre")
    folder_titles = folder_candidates(path, performer_name)
    if folder_titles and "hegre" in stem.casefold():
        title = titlecase_loose_text(folder_titles[0])
        if not is_weak_title(title):
            date, _ = detect_date(stem)
            return ParsedSceneMetadata(title=title, date=date, confidence="high", rename_safe=True, family="hegre-folder")
    return None


def parse_onlyfans(path: Path, performer_name: str) -> ParsedSceneMetadata | None:
    stem = path.stem
    patterns = (
        rf"^{re.escape(performer_name)}\s*-\s*\[(?:OF|OF-Shorts)[^\]]*\]\s*-\s*(?:\[(20\d{{2}})\]\s*-\s*)?(.+)$",
        rf"^\[(?:OnlyFans(?:\.com)?|OnlyFans)\]\s*{re.escape(performer_name)}\s*-\s*(.+)$",
        rf"^\[OF-[^\]]+\]\s*(.+)$",
        rf"^OnlyFans\s*-\s*{re.escape(performer_name)}\s*-\s*(.+)$",
        rf"^\[OnlyFans\]\s*-\s*{re.escape(performer_name)}\s*(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, stem, flags=re.IGNORECASE)
        if not match:
            continue
        raw_title = match.group(match.lastindex or 1)
        title = titlecase_loose_text(cleanup_filename_component(raw_title))
        title = re.sub(r"\s+\[\]$", "", title).strip()
        title = re.sub(r"\s*-\s*\d{2,3}-\d{2,3}$", "", title).strip()
        title = re.sub(r"\s*\((20\d{2})\)$", "", title).strip()
        title = re.sub(r"\b\d{4}\b$", "", title).strip(" -")
        if is_weak_title(title) or has_noisy_title_markers(title):
            continue
        date, _ = detect_date(stem)
        return ParsedSceneMetadata(title=title, date=date, confidence="high", rename_safe=not pack_like(path), family="onlyfans")
    return None


def parse_momsfamily(path: Path, performer_name: str) -> ParsedSceneMetadata | None:
    stem = path.stem
    match = re.search(
        rf"\[MomsFamilySecrets\.com\].*?-\s*(.*?)\s*$",
        stem,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    title = titlecase_loose_text(cleanup_filename_component(match.group(1)))
    if is_weak_title(title):
        return None
    date_match = re.search(r"\((\w{3}) (\d{1,2}), (20\d{2})\)", path.as_posix(), flags=re.IGNORECASE)
    month_map = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    date = ""
    if date_match:
        date = f"{date_match.group(3)}-{month_map[date_match.group(1)[:3].casefold()]}-{int(date_match.group(2)):02d}"
    elif re.search(r"\b(\d{2})\.(\d{2})\.(\d{2})\b", stem):
        short = re.search(r"\b(\d{2})\.(\d{2})\.(\d{2})\b", stem)
        assert short is not None
        date = short_date_to_iso(short)
    if is_weak_title(title):
        return None
    return ParsedSceneMetadata(title=title, date=date, confidence="high", rename_safe=True, family="momsfamily")


def parse_parenthesized_title(path: Path, performer_name: str) -> ParsedSceneMetadata | None:
    match = re.search(rf"^{re.escape(performer_name)}\s*\(\s*([^)]+?)\s*\)", path.stem, flags=re.IGNORECASE)
    if not match:
        return None
    title = titlecase_loose_text(cleanup_filename_component(match.group(1)))
    if is_weak_title(title):
        return None
    return ParsedSceneMetadata(title=title, date="", confidence="high", rename_safe=True, family="parenthesized")


def parse_folder_based(path: Path, performer_name: str) -> ParsedSceneMetadata | None:
    candidates = folder_candidates(path, performer_name)
    if not candidates:
        return None
    stem = cleanup_filename_component(strip_performer_name(path.stem, performer_name))
    if stem and not is_weak_title(stem) and len(stem.split()) > 2:
        return None
    title = titlecase_loose_text(candidates[0])
    if not looks_like_clean_scene_title(title):
        return None
    return ParsedSceneMetadata(title=title, date="", confidence="medium", rename_safe=False, family="folder")


def parse_dotted_dump(path: Path, performer_name: str) -> ParsedSceneMetadata | None:
    stem = path.stem
    if "." not in stem and "_" not in stem:
        return None
    date, remaining = detect_date(stem)
    cleaned = cleanup_filename_component(strip_performer_name(remaining, performer_name))
    candidates = folder_candidates(path, performer_name)
    if candidates:
        title = titlecase_loose_text(candidates[0])
        safe = looks_like_clean_scene_title(title) and not pack_like(path)
        confidence = "medium" if safe else "low"
        return ParsedSceneMetadata(title=title, date=date, confidence=confidence, rename_safe=safe, family="dump-folder")
    title = titlecase_loose_text(cleaned)
    if is_weak_title(title):
        return None
    title = re.sub(r"^Hegre\s+", "", title, flags=re.IGNORECASE)
    safe = looks_like_clean_scene_title(title) and not pack_like(path)
    confidence = "medium" if safe else "low"
    return ParsedSceneMetadata(title=title, date=date, confidence=confidence, rename_safe=safe, family="dump")


def parse_generic(path: Path, performer_name: str) -> ParsedSceneMetadata:
    date, remaining = detect_date(path.stem)
    title = titlecase_loose_text(cleanup_filename_component(strip_performer_name(remaining, performer_name)))
    if is_weak_title(title):
        candidates = folder_candidates(path, performer_name)
        title = titlecase_loose_text(candidates[0]) if candidates else ""
    safe = False
    return ParsedSceneMetadata(
        title=title,
        date=date,
        confidence="low",
        rename_safe=safe,
        family="generic",
    )


def derive_metadata(file_path: str, performer_name: str) -> ParsedSceneMetadata:
    path = Path(file_path)
    for handler in (
        parse_hegre,
        parse_onlyfans,
        parse_momsfamily,
        parse_parenthesized_title,
        parse_folder_based,
        parse_dotted_dump,
    ):
        parsed = handler(path, performer_name)
        if parsed and parsed.title and not is_weak_title(parsed.title):
            return parsed
    return parse_generic(path, performer_name)
