#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import parse, request


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
PACK_WORDS = {
    "pack",
    "megapack",
    "compilation",
    "collection",
    "imageset",
    "photoset",
}
DEFAULT_REPORT_ROOT = Path("/home/raphh/docker/appdata/nsfw-automation/reports")


@dataclass
class Candidate:
    title: str
    payload: dict[str, Any]
    resolution: int
    normalized_title: str
    source: str


def resolution_rank(title: str) -> int:
    for pattern, score in RESOLUTION_PATTERNS:
        if pattern.search(title):
            return score
    return 0


def build_performer_words(performer: str | None) -> set[str]:
    if not performer:
        return set()
    return {word for word in TOKEN_RE.split(performer.lower()) if word}


def is_packlike(title: str) -> bool:
    words = {word for word in TOKEN_RE.split(title.lower()) if word}
    return any(word in PACK_WORDS for word in words)


def normalize_title(title: str, performer: str | None = None) -> str:
    value = BRACKETED_RE.sub(" ", title)
    value = DATE_RE.sub(" ", value)
    value = value.replace("&", " and ")
    value = TOKEN_RE.sub(" ", value.lower())
    words = [word for word in SPACE_RE.split(value.strip()) if word]
    performer_words = build_performer_words(performer)

    cleaned: list[str] = []
    for word in words:
        if len(word) == 1:
            continue
        if word in performer_words:
            continue
        if word in NOISE_WORDS:
            continue
        if word.isdigit() and len(word) == 4:
            continue
        cleaned.append(word)

    return " ".join(cleaned).strip()


def iter_candidate_objects(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("releases", "items", "candidates", "results", "keep", "drop"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError("input JSON must be a list of objects or a dict containing releases/items/candidates/results")


def pick_title(payload: dict[str, Any]) -> str:
    for key in ("title", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(f"candidate is missing title/name: {payload!r}")


def build_candidates(items: list[dict[str, Any]], performer: str | None = None) -> list[Candidate]:
    candidates: list[Candidate] = []
    for item in items:
        title = pick_title(item)
        candidates.append(
            Candidate(
                title=title,
                payload=item,
                resolution=resolution_rank(title),
                normalized_title=normalize_title(title, performer),
                source=infer_source(item),
            )
        )
    return candidates


def sort_key(candidate: Candidate) -> tuple[int, int, str]:
    size = candidate.payload.get("size")
    size_value = int(size) if isinstance(size, int) else 0
    return (candidate.resolution, size_value, candidate.title.casefold())


def dedupe_candidates(candidates: list[Candidate]) -> dict[str, Any]:
    groups: dict[str, list[Candidate]] = {}
    passthrough: list[Candidate] = []
    for candidate in candidates:
        if not candidate.normalized_title or is_packlike(candidate.title):
            passthrough.append(candidate)
            continue
        groups.setdefault(candidate.normalized_title, []).append(candidate)

    keep: list[dict[str, Any]] = [candidate.payload for candidate in passthrough]
    drop: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []

    for normalized_title, grouped in sorted(groups.items()):
        grouped_sorted = sorted(grouped, key=sort_key, reverse=True)
        best = grouped_sorted[0]
        keep.append(best.payload)

        distinct_resolutions = {candidate.resolution for candidate in grouped_sorted}
        if len(grouped_sorted) == 1:
            continue

        group_report = {
            "normalized_title": normalized_title,
            "keep": {
                "title": best.title,
                "resolution": best.resolution,
            },
            "drop": [
                {
                    "title": candidate.title,
                    "resolution": candidate.resolution,
                }
                for candidate in grouped_sorted[1:]
            ],
        }

        if len(distinct_resolutions) > 1:
            drop.extend(candidate.payload for candidate in grouped_sorted[1:] if candidate.resolution < best.resolution)
        else:
            review.append(group_report)

    return {
        "keep": keep,
        "drop": drop,
        "review": review,
    }


def infer_source(payload: dict[str, Any]) -> str:
    for key in ("source", "tracker", "comment", "url", "link", "download_url"):
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        lowered = value.casefold()
        if "bitporn" in lowered:
            return "bitporn"
        if "happyfappy" in lowered:
            return "happyfappy"
    return "unknown"


def source_priority(source: str) -> int:
    if source == "bitporn":
        return 2
    if source == "happyfappy":
        return 1
    return 0


def http_json(url: str, method: str = "GET", data: bytes | None = None) -> Any:
    req = request.Request(url, method=method, data=data)
    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def http_post_form(url: str, fields: dict[str, str]) -> None:
    data = parse.urlencode(fields).encode("utf-8")
    req = request.Request(url, method="POST", data=data)
    with request.urlopen(req) as response:
        response.read()


def fetch_qbit_torrents(base_url: str, category: str) -> list[dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/api/v2/torrents/info?category={parse.quote(category)}"
    payload = http_json(url)
    if not isinstance(payload, list):
        raise ValueError("unexpected qBittorrent response")
    return [item for item in payload if isinstance(item, dict)]


def performer_filter(torrents: list[dict[str, Any]], performer: str) -> list[dict[str, Any]]:
    suffix = f"/{performer}"
    return [
        torrent
        for torrent in torrents
        if isinstance(torrent.get("save_path"), str) and torrent["save_path"].rstrip("/").endswith(suffix)
    ]


def performer_from_save_path(save_path: str) -> str | None:
    cleaned = save_path.rstrip("/")
    prefix = "/data/torrents/nsfw/"
    if not cleaned.startswith(prefix):
        return None
    performer = cleaned[len(prefix):].split("/", 1)[0].strip()
    return performer or None


def group_torrents_by_performer(torrents: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for torrent in torrents:
        save_path = torrent.get("save_path")
        if not isinstance(save_path, str):
            continue
        performer = performer_from_save_path(save_path)
        if not performer:
            continue
        grouped.setdefault(performer, []).append(torrent)
    return grouped


def build_torrent_candidates(torrents: list[dict[str, Any]], performer: str) -> list[Candidate]:
    candidates: list[Candidate] = []
    for torrent in torrents:
        title = str(torrent.get("name", "")).strip()
        if not title:
            continue
        candidates.append(
            Candidate(
                title=title,
                payload=torrent,
                resolution=resolution_rank(title),
                normalized_title=normalize_title(title, performer),
                source=infer_source(torrent),
            )
        )
    return candidates


def summarize_candidate(candidate: Candidate) -> dict[str, Any]:
    summary = {
        "title": candidate.title,
        "source": candidate.source,
        "resolution": candidate.resolution,
    }
    for key in ("id", "hash", "size", "comment", "tracker", "download_url", "url", "link"):
        value = candidate.payload.get(key)
        if value is not None:
            summary[key] = value
    return summary


def additions_plan(
    incoming: list[Candidate],
    existing: list[Candidate],
) -> dict[str, Any]:
    existing_by_title: dict[str, list[Candidate]] = {}
    for candidate in existing:
        if not candidate.normalized_title:
            continue
        existing_by_title.setdefault(candidate.normalized_title, []).append(candidate)

    incoming_groups: dict[str, list[Candidate]] = {}
    passthrough: list[Candidate] = []
    for candidate in incoming:
        if not candidate.normalized_title or is_packlike(candidate.title):
            passthrough.append(candidate)
            continue
        incoming_groups.setdefault(candidate.normalized_title, []).append(candidate)

    add_now: list[dict[str, Any]] = [summarize_candidate(candidate) for candidate in passthrough]
    hold_for_crossseed: list[dict[str, Any]] = []
    skip_existing: list[dict[str, Any]] = []
    manual_review: list[dict[str, Any]] = []

    for normalized_title, grouped in sorted(incoming_groups.items()):
        grouped_sorted = sorted(
            grouped,
            key=lambda candidate: (
                candidate.resolution,
                source_priority(candidate.source),
                int(candidate.payload.get("size", 0)) if isinstance(candidate.payload.get("size"), int) else 0,
                candidate.title.casefold(),
            ),
            reverse=True,
        )
        best = grouped_sorted[0]
        existing_matches = existing_by_title.get(normalized_title, [])
        existing_sources = {candidate.source for candidate in existing_matches}

        if existing_matches:
            same_source_matches = [candidate for candidate in existing_matches if candidate.source == best.source]
            same_source_max_resolution = max(
                (candidate.resolution for candidate in same_source_matches),
                default=-1,
            )
            existing_max_resolution = max(
                (candidate.resolution for candidate in existing_matches),
                default=-1,
            )

            if best.source == "happyfappy" and "bitporn" in existing_sources and best.resolution <= existing_max_resolution:
                hold_for_crossseed.append(
                    {
                        "normalized_title": normalized_title,
                        "candidate": summarize_candidate(best),
                        "existing_primary": [summarize_candidate(candidate) for candidate in existing_matches],
                        "reason": "bitporn_exists",
                    }
                )
            elif same_source_matches and same_source_max_resolution >= best.resolution:
                skip_existing.append(
                    {
                        "normalized_title": normalized_title,
                        "candidate": summarize_candidate(best),
                        "existing": [summarize_candidate(candidate) for candidate in existing_matches],
                    }
                )
            else:
                add_now.append(summarize_candidate(best))
        else:
            add_now.append(summarize_candidate(best))

        for candidate in grouped_sorted[1:]:
            if candidate.source == "happyfappy" and any(
                primary.source == "bitporn" for primary in grouped_sorted if primary is not candidate
            ):
                hold_for_crossseed.append(
                    {
                        "normalized_title": normalized_title,
                        "candidate": summarize_candidate(candidate),
                        "reason": "bitporn_candidate_selected",
                    }
                )
            elif candidate.resolution < best.resolution:
                skip_existing.append(
                    {
                        "normalized_title": normalized_title,
                        "candidate": summarize_candidate(candidate),
                        "reason": "lower_resolution_than_selected",
                    }
                )
            else:
                manual_review.append(
                    {
                        "normalized_title": normalized_title,
                        "candidates": [summarize_candidate(item) for item in grouped_sorted],
                    }
                )
                break

    return {
        "add_now": add_now,
        "hold_for_crossseed": hold_for_crossseed,
        "skip_existing": skip_existing,
        "manual_review": manual_review,
    }


def qbit_prune_plan(torrents: list[dict[str, Any]], performer: str) -> dict[str, Any]:
    candidates = build_torrent_candidates(torrents, performer)
    groups: dict[str, list[Candidate]] = {}
    skipped: list[str] = []

    for candidate in candidates:
        if not candidate.normalized_title or is_packlike(candidate.title):
            skipped.append(candidate.title)
            continue
        groups.setdefault(candidate.normalized_title, []).append(candidate)

    planned_deletions: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []

    for normalized_title, grouped in sorted(groups.items()):
        if len(grouped) < 2:
            continue

        grouped_sorted = sorted(grouped, key=sort_key, reverse=True)
        best = grouped_sorted[0]
        lower_res = [candidate for candidate in grouped_sorted[1:] if candidate.resolution < best.resolution]

        if lower_res:
            planned_deletions.append(
                {
                    "normalized_title": normalized_title,
                    "keep": {
                        "title": best.title,
                        "hash": best.payload.get("hash"),
                        "resolution": best.resolution,
                    },
                    "delete": [
                        {
                            "title": candidate.title,
                            "hash": candidate.payload.get("hash"),
                            "resolution": candidate.resolution,
                            "state": candidate.payload.get("state"),
                            "progress": candidate.payload.get("progress"),
                        }
                        for candidate in lower_res
                    ],
                }
            )
            continue

        review.append(
            {
                "normalized_title": normalized_title,
                "entries": [
                    {
                        "title": candidate.title,
                        "hash": candidate.payload.get("hash"),
                        "resolution": candidate.resolution,
                    }
                    for candidate in grouped_sorted
                ],
            }
        )

    return {
        "performer": performer,
        "delete_groups": planned_deletions,
        "review_groups": review,
        "skipped_titles": skipped,
    }


def qbit_crossseed_cleanup_plan(torrents: list[dict[str, Any]], performer: str) -> dict[str, Any]:
    candidates = build_torrent_candidates(torrents, performer)
    by_group_key: dict[str, list[Candidate]] = {}
    skipped_titles: list[str] = []

    for candidate in candidates:
        key = candidate.normalized_title or candidate.title.casefold().strip()
        if not key or is_packlike(candidate.title):
            skipped_titles.append(candidate.title)
            continue
        by_group_key.setdefault(key, []).append(candidate)

    delete_groups: list[dict[str, Any]] = []
    review_groups: list[dict[str, Any]] = []

    for group_key, grouped in sorted(by_group_key.items()):
        bitporn = [candidate for candidate in grouped if candidate.source == "bitporn"]
        happyfappy = [candidate for candidate in grouped if candidate.source == "happyfappy"]
        if not bitporn or not happyfappy:
            continue

        bitporn_sizes = {candidate.payload.get("size") for candidate in bitporn}
        happyfappy_sizes = {candidate.payload.get("size") for candidate in happyfappy}
        size_overlap = bool(bitporn_sizes & happyfappy_sizes)
        bitporn_resolutions = {candidate.resolution for candidate in bitporn}
        happyfappy_resolutions = {candidate.resolution for candidate in happyfappy}
        same_resolution = bool(bitporn_resolutions & happyfappy_resolutions)

        report = {
            "normalized_title": grouped[0].normalized_title,
            "title": grouped[0].title,
            "bitporn": [summarize_candidate(candidate) for candidate in bitporn],
            "happyfappy": [summarize_candidate(candidate) for candidate in happyfappy],
            "size_overlap": size_overlap,
            "same_resolution": same_resolution,
        }

        if size_overlap or same_resolution:
            delete_groups.append(report)
        else:
            review_groups.append(report)

    return {
        "performer": performer,
        "delete_groups": delete_groups,
        "review_groups": review_groups,
        "skipped_titles": skipped_titles,
    }


def delete_torrents(base_url: str, hashes: list[str], delete_files: bool) -> None:
    if not hashes:
        return
    http_post_form(
        f"{base_url.rstrip('/')}/api/v2/torrents/delete",
        {
            "hashes": "|".join(hashes),
            "deleteFiles": "true" if delete_files else "false",
        },
    )


def candidate_url(payload: dict[str, Any]) -> str | None:
    for key in ("download_url", "url", "link", "magnet_uri", "magnet"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def add_torrents(
    base_url: str,
    urls: list[str],
    category: str,
    save_path: str,
    paused: bool,
) -> None:
    if not urls:
        return
    http_post_form(
        f"{base_url.rstrip('/')}/api/v2/torrents/add",
        {
            "urls": "\n".join(urls),
            "category": category,
            "savepath": save_path,
            "paused": "true" if paused else "false",
        },
    )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "unknown"


def default_phase1_output(performer: str, filename: str, report_root: Path) -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return report_root / "phase1-add-performer" / slugify(performer) / run_id / filename


def emit_json(payload: dict[str, Any], output: Path | None = None) -> None:
    text = json.dumps(payload, indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        sys.stdout.write(json.dumps({"json": str(output)}, indent=2) + "\n")
    else:
        sys.stdout.write(text)


def cmd_select(args: argparse.Namespace) -> int:
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    items = iter_candidate_objects(payload)
    candidates = build_candidates(items, args.performer)
    result = dedupe_candidates(candidates)
    emit_json(result, args.output)
    return 0


def cmd_plan_additions(args: argparse.Namespace) -> int:
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    items = iter_candidate_objects(payload)
    incoming = build_candidates(items, args.performer)
    existing = performer_filter(fetch_qbit_torrents(args.qbit_url, args.category), args.performer)
    existing_candidates = build_torrent_candidates(existing, args.performer)
    result = additions_plan(incoming, existing_candidates)
    output = args.output or default_phase1_output(args.performer, "addition-plan.json", args.report_root)
    emit_json(result, output)
    return 0


def cmd_apply_plan(args: argparse.Namespace) -> int:
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    add_now = payload.get("add_now")
    if not isinstance(add_now, list):
        raise ValueError("plan JSON must contain an add_now list")

    urls: list[str] = []
    missing_urls: list[dict[str, Any]] = []
    for item in add_now:
        if not isinstance(item, dict):
            continue
        url = candidate_url(item)
        if url:
            urls.append(url)
        else:
            missing_urls.append(item)

    save_path = f"{args.save_root.rstrip('/')}/{args.performer}"
    if args.apply:
        add_torrents(
            args.qbit_url,
            urls,
            category=args.category,
            save_path=save_path,
            paused=args.paused,
        )

    result = {
        "performer": args.performer,
        "save_path": save_path,
        "category": args.category,
        "applied": bool(args.apply),
        "queued_count": len(urls),
        "queued_titles": [item.get("title") for item in add_now if isinstance(item, dict) and candidate_url(item)],
        "missing_url_count": len(missing_urls),
        "missing_urls": missing_urls,
    }
    output = args.output or default_phase1_output(args.performer, "queue-result.json", args.report_root)
    emit_json(result, output)
    return 0


def cmd_qbit_prune(args: argparse.Namespace) -> int:
    torrents = performer_filter(fetch_qbit_torrents(args.qbit_url, args.category), args.performer)
    plan = qbit_prune_plan(torrents, args.performer)

    if args.apply:
        hashes = [
            str(item["hash"])
            for group in plan["delete_groups"]
            for item in group["delete"]
            if item.get("hash")
        ]
        delete_torrents(args.qbit_url, hashes, delete_files=args.delete_files)

    emit_json(plan, args.output)
    return 0


def cmd_qbit_cleanup_crossseed(args: argparse.Namespace) -> int:
    torrents = performer_filter(fetch_qbit_torrents(args.qbit_url, args.category), args.performer)
    plan = qbit_crossseed_cleanup_plan(torrents, args.performer)

    if args.apply:
        hashes = [
            str(item["hash"])
            for group in plan["delete_groups"]
            for item in group["happyfappy"]
            if item.get("hash")
        ]
        delete_torrents(args.qbit_url, hashes, delete_files=args.delete_files)

    emit_json(plan, args.output)
    return 0


def cmd_qbit_prune_all(args: argparse.Namespace) -> int:
    torrents = fetch_qbit_torrents(args.qbit_url, args.category)
    grouped = group_torrents_by_performer(torrents)

    plans: list[dict[str, Any]] = []
    hashes_to_delete: list[str] = []
    for performer in sorted(grouped):
        plan = qbit_prune_plan(grouped[performer], performer)
        if plan["delete_groups"] or plan["review_groups"]:
            plans.append(plan)
        for group in plan["delete_groups"]:
            for item in group["delete"]:
                if item.get("hash"):
                    hashes_to_delete.append(str(item["hash"]))

    if args.apply:
        delete_torrents(args.qbit_url, hashes_to_delete, delete_files=args.delete_files)

    result = {
        "performers": plans,
        "delete_count": len(hashes_to_delete),
        "applied": bool(args.apply),
        "delete_files": bool(args.delete_files),
    }
    emit_json(result, args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Choose highest-resolution NSFW releases and prune lower-quality qBittorrent duplicates."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    select_parser = subparsers.add_parser("select", help="Keep only the best-resolution candidate per normalized title")
    select_parser.add_argument("input", type=Path, help="Path to a JSON file containing release candidate objects")
    select_parser.add_argument("--performer", help="Canonical performer name to strip from titles while deduping")
    select_parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    select_parser.set_defaults(func=cmd_select)

    plan_parser = subparsers.add_parser(
        "plan-additions",
        help="Plan adds with BitPorn-first priority and hold HappyFappy duplicates for later cross-seed",
    )
    plan_parser.add_argument("input", type=Path, help="Path to a JSON file containing release candidate objects")
    plan_parser.add_argument("--performer", required=True, help="Canonical performer name to strip from titles while deduping")
    plan_parser.add_argument("--qbit-url", default="http://127.0.0.1:8085", help="Base URL of qBittorrent Web API")
    plan_parser.add_argument("--category", default="nsfw", help="qBittorrent category to inspect")
    plan_parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    plan_parser.add_argument("--output", type=Path, help="Write JSON to this path instead of the default Phase 1 report path")
    plan_parser.set_defaults(func=cmd_plan_additions)

    apply_parser = subparsers.add_parser(
        "apply-plan",
        help="Queue only the add_now items from a plan-additions result into qBittorrent",
    )
    apply_parser.add_argument("input", type=Path, help="Path to a JSON file produced by plan-additions")
    apply_parser.add_argument("--performer", required=True, help="Canonical performer folder name")
    apply_parser.add_argument("--qbit-url", default="http://127.0.0.1:8085", help="Base URL of qBittorrent Web API")
    apply_parser.add_argument("--category", default="nsfw", help="qBittorrent category to set on queued torrents")
    apply_parser.add_argument("--save-root", default="/data/torrents/nsfw", help="Base qBittorrent save root")
    apply_parser.add_argument("--paused", action="store_true", help="Add torrents in paused state")
    apply_parser.add_argument("--apply", action="store_true", help="Actually queue the torrents instead of only reporting")
    apply_parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    apply_parser.add_argument("--output", type=Path, help="Write JSON to this path instead of the default Phase 1 report path")
    apply_parser.set_defaults(func=cmd_apply_plan)

    prune_parser = subparsers.add_parser("qbit-prune", help="Find and optionally delete lower-resolution qBittorrent duplicates")
    prune_parser.add_argument("--performer", required=True, help="Canonical performer folder name")
    prune_parser.add_argument("--qbit-url", default="http://127.0.0.1:8085", help="Base URL of qBittorrent Web API")
    prune_parser.add_argument("--category", default="nsfw", help="qBittorrent category to inspect")
    prune_parser.add_argument("--apply", action="store_true", help="Delete the lower-resolution torrents instead of only reporting")
    prune_parser.add_argument("--delete-files", action="store_true", help="Delete payload files along with torrents")
    prune_parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    prune_parser.set_defaults(func=cmd_qbit_prune)

    cleanup_parser = subparsers.add_parser(
        "qbit-cleanup-crossseed",
        help="Remove HappyFappy torrents that exactly duplicate an existing BitPorn title for cross-seed testing",
    )
    cleanup_parser.add_argument("--performer", required=True, help="Canonical performer folder name")
    cleanup_parser.add_argument("--qbit-url", default="http://127.0.0.1:8085", help="Base URL of qBittorrent Web API")
    cleanup_parser.add_argument("--category", default="nsfw", help="qBittorrent category to inspect")
    cleanup_parser.add_argument("--apply", action="store_true", help="Delete the redundant HappyFappy torrents instead of only reporting")
    cleanup_parser.add_argument("--delete-files", action="store_true", help="Delete payload files along with torrents")
    cleanup_parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    cleanup_parser.set_defaults(func=cmd_qbit_cleanup_crossseed)

    prune_all_parser = subparsers.add_parser(
        "qbit-prune-all",
        help="Find and optionally delete lower-resolution qBittorrent duplicates across all nsfw performers",
    )
    prune_all_parser.add_argument("--qbit-url", default="http://127.0.0.1:8085", help="Base URL of qBittorrent Web API")
    prune_all_parser.add_argument("--category", default="nsfw", help="qBittorrent category to inspect")
    prune_all_parser.add_argument("--apply", action="store_true", help="Delete the lower-resolution torrents instead of only reporting")
    prune_all_parser.add_argument("--delete-files", action="store_true", help="Delete payload files along with torrents")
    prune_all_parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    prune_all_parser.set_defaults(func=cmd_qbit_prune_all)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
