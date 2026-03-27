#!/usr/bin/env python3

"""Pick qBittorrent cross-seed releases and upload via Upload Assistant.

Flow:
1) Pick tracker code to upload to.
2) Pick media scope (movie/tv/both).
3) Pick one or more releases from the candidate list.
4) Upload with Upload Assistant and add `upload` qBittorrent tag.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


TV_NAME_RE = re.compile(
    r"(?:"
    r"\bS\d{1,2}E\d{1,2}\b|"
    r"\bS\d{1,2}\b|"
    r"\bE\d{2}\b|"
    r"\b\d{1,2}x\d{1,2}\b|"
    r"\bSeason\b|"
    r"\bComplete\s+Season\b|"
    r"\bComplete\s+Series\b|"
    r"\bMini[- ]?Series\b"
    r")",
    re.IGNORECASE,
)

ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


FALLBACK_TRACKER_PATTERNS: Dict[str, List[str]] = {
    "ANT": ["anthelion.me", "tracker.anthelion.me", "anthelion"],
    "AITHER": ["aither.cc", "aither"],
    "BLU": ["blutopia.cc", "blutopia"],
}


@dataclass
class Candidate:
    index: int
    torrent_hash: str
    name: str
    media_type: str
    size_bytes: int
    source_hosts: List[str]
    content_path: str
    tags: List[str]


class QBitAPI:
    def __init__(self, base_url: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._tracker_host_cache: Dict[str, Set[str]] = {}

    def get_json(self, path: str, params: Optional[Dict[str, str]] = None):
        url = f"{self.base_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url=url, method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_torrents(self, category: str) -> List[dict]:
        return self.get_json("/api/v2/torrents/info", {"category": category})

    def get_tracker_hosts(self, torrent: dict) -> Set[str]:
        torrent_hash = torrent.get("hash", "")
        if torrent_hash in self._tracker_host_cache:
            return self._tracker_host_cache[torrent_hash]

        hosts: Set[str] = set()
        primary = parse_tracker_host(torrent.get("tracker", ""))
        if primary:
            hosts.add(primary)

        needs_lookup = int(torrent.get("trackers_count", 1)) > 1 or not hosts
        if needs_lookup and torrent_hash:
            try:
                tracker_rows = self.get_json("/api/v2/torrents/trackers", {"hash": torrent_hash})
            except Exception:
                tracker_rows = []
            for row in tracker_rows:
                if not isinstance(row, dict):
                    continue
                host = parse_tracker_host(row.get("url", ""))
                if host:
                    hosts.add(host)

        self._tracker_host_cache[torrent_hash] = hosts
        return hosts


def parse_tracker_host(url: str) -> str:
    if not isinstance(url, str):
        return ""
    url = url.strip()
    if not url.startswith("http"):
        return ""
    return urllib.parse.urlparse(url).netloc.lower()


def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    return " ".join(name.casefold().split())


def torrent_key(torrent: dict) -> Tuple[str, int]:
    return (normalize_name(torrent.get("name", "")), int(torrent.get("size", 0) or 0))


def split_tags(tag_str: str) -> List[str]:
    if not tag_str:
        return []
    return [part.strip() for part in str(tag_str).split(",") if part.strip()]


def hosts_match_tracker(hosts: Iterable[str], patterns: Sequence[str]) -> bool:
    lowered_patterns = [p.lower() for p in patterns if p]
    for host in hosts:
        host = host.lower()
        for pattern in lowered_patterns:
            if pattern in host:
                return True
    return False


def classify_media(torrent: dict, movie_keys: Set[Tuple[str, int]], tv_keys: Set[Tuple[str, int]]) -> str:
    key = torrent_key(torrent)
    if key in movie_keys and key not in tv_keys:
        return "movie"
    if key in tv_keys and key not in movie_keys:
        return "tv"

    name = str(torrent.get("name", ""))
    if TV_NAME_RE.search(name):
        return "tv"
    return "movie"


def media_in_scope(media_type: str, scope: str) -> bool:
    if scope == "both":
        return True
    return media_type == scope


def human_gib(size_bytes: int) -> str:
    return f"{(size_bytes / (1024 ** 3)):.2f} GiB"


def get_ua_configured_trackers(container: str, python_bin: str) -> List[str]:
    code = (
        "import json;"
        "from data.config import config;"
        "print(json.dumps(sorted(config.get('TRACKERS', {}).keys())))"
    )
    cmd = ["docker", "exec", "-i", container, python_bin, "-c", code]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []
    output = result.stdout.strip().splitlines()
    if not output:
        return []
    try:
        trackers = json.loads(output[-1])
    except json.JSONDecodeError:
        return []
    return [str(item).upper() for item in trackers if str(item).strip()]


def get_tracker_patterns_from_ua(container: str, python_bin: str, tracker_code: str) -> List[str]:
    code = (
        "import json, sys, urllib.parse;"
        "from data.config import config;"
        "from src.trackersetup import tracker_class_map;"
        "tracker_code=sys.argv[1].upper();"
        "patterns=set();"
        "tracker_cls=tracker_class_map.get(tracker_code);"
        ""
        "\nif tracker_cls is not None:\n"
        "    tracker=tracker_cls(config)\n"
        "    for attr in ('base_url','search_url','upload_url','id_url','requests_url'):\n"
        "        value=getattr(tracker, attr, None)\n"
        "        if isinstance(value, str) and value.startswith('http'):\n"
        "            host=urllib.parse.urlparse(value).netloc.lower()\n"
        "            if host:\n"
        "                patterns.add(host)\n"
        "print(json.dumps(sorted(patterns)))"
    )
    cmd = ["docker", "exec", "-i", container, python_bin, "-c", code, tracker_code]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []
    output = result.stdout.strip().splitlines()
    if not output:
        return []
    try:
        patterns = json.loads(output[-1])
    except json.JSONDecodeError:
        return []
    return [str(item).lower() for item in patterns if str(item).strip()]


def resolve_tracker_patterns(container: str, python_bin: str, tracker_code: str) -> List[str]:
    tracker_code = tracker_code.upper()
    patterns = get_tracker_patterns_from_ua(container, python_bin, tracker_code)
    if not patterns:
        patterns = FALLBACK_TRACKER_PATTERNS.get(tracker_code, [])
    return sorted(set(patterns))


def categories_for_exclusion(scope: str) -> List[str]:
    categories = ["cross-seed", "movies"]
    if scope in {"tv", "both"}:
        categories.append("tvshows")
    return categories


def parse_selection(selection: str, max_index: int) -> List[int]:
    cleaned = selection.strip().lower()
    if cleaned == "all":
        return list(range(1, max_index + 1))

    chosen: Set[int] = set()
    for chunk in selection.split(","):
        part = chunk.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            start = int(left)
            end = int(right)
            if start > end:
                start, end = end, start
            for value in range(start, end + 1):
                chosen.add(value)
        else:
            chosen.add(int(part))

    invalid = [value for value in chosen if value < 1 or value > max_index]
    if invalid:
        raise ValueError(f"Invalid selection indexes: {sorted(invalid)}")
    return sorted(chosen)


def prompt_tracker_code(configured_trackers: Sequence[str], preselected: Optional[str]) -> str:
    if preselected:
        return preselected.upper()

    if configured_trackers:
        print("Configured tracker codes in Upload Assistant:")
        print("  " + ", ".join(configured_trackers))
    else:
        print("Could not read tracker codes from Upload Assistant config.")
        print("Enter a tracker code manually (e.g. ANT, BLU, AITHER).")

    while True:
        value = input("Target tracker code: ").strip().upper()
        if not value:
            continue
        if configured_trackers and value not in configured_trackers:
            print(f"'{value}' is not in configured trackers. Try again.")
            continue
        return value


def prompt_media_scope(preselected: Optional[str]) -> str:
    if preselected:
        return preselected

    print("Media scope:")
    print("  1) movie")
    print("  2) tv")
    print("  3) both")
    mapping = {"1": "movie", "2": "tv", "3": "both", "movie": "movie", "tv": "tv", "both": "both"}
    while True:
        value = input("Pick media scope [1/2/3]: ").strip().lower()
        if value in mapping:
            return mapping[value]
        print("Invalid choice.")


def print_candidates(candidates: Sequence[Candidate], limit: int) -> None:
    to_show = list(candidates[:limit]) if limit > 0 else list(candidates)
    if not to_show:
        print("No candidates to show.")
        return

    idx_width = max(3, len(str(to_show[-1].index)))
    print()
    print(f"{'#':>{idx_width}}  {'Type':<5}  {'Size':>10}  {'Source':<28}  Name")
    print("-" * (idx_width + 2 + 5 + 2 + 10 + 2 + 28 + 2 + 64))
    for candidate in to_show:
        name = candidate.name
        source = ",".join(candidate.source_hosts[:2])
        if len(candidate.source_hosts) > 2:
            source += f"+{len(candidate.source_hosts) - 2}"
        if len(name) > 96:
            name = name[:93] + "..."
        print(
            f"{candidate.index:>{idx_width}}  "
            f"{candidate.media_type:<5}  "
            f"{human_gib(candidate.size_bytes):>10}  "
            f"{source:<28}  "
            f"{name}"
        )

    if limit > 0 and len(candidates) > limit:
        print(f"\nShowing first {limit} of {len(candidates)} candidates. Increase --limit to see more.")


def build_upload_command(
    container: str,
    python_bin: str,
    upload_script: str,
    candidate: Candidate,
    tracker_code: str,
    client_name: str,
    qbit_tag: str,
    qbit_category: str,
    ua_interactive: bool,
    extra_args: Optional[str],
) -> List[str]:
    cmd = [
        "docker",
        "exec",
        "-i",
        container,
        python_bin,
        upload_script,
        candidate.content_path,
        "--trackers",
        tracker_code,
        "--client",
        client_name,
        "-qbt",
        qbit_tag,
        "-qbc",
        qbit_category,
    ]
    if not ua_interactive:
        cmd.append("-ua")
    if extra_args:
        cmd.extend(shlex.split(extra_args))
    return cmd


def has_tracker_data_error(output: str, tracker_code: str) -> bool:
    cleaned = ANSI_RE.sub("", output)
    pattern = re.compile(rf"^\s*{re.escape(tracker_code)}\s*:\s*data\s+error", re.IGNORECASE | re.MULTILINE)
    return bool(pattern.search(cleaned))


def detect_skip_reason(output: str, tracker_code: str) -> Optional[str]:
    cleaned = ANSI_RE.sub("", output)
    lowered = cleaned.lower()

    if f"found potential dupes on: {tracker_code.lower()}" in lowered:
        return "dupe"
    if "exact same media file already exists" in lowered or "same infohash already exists" in lowered:
        return "dupe"
    if "not enough successful trackers" in lowered or "no uploads being processed" in lowered:
        return "precheck"
    return None


def run_and_stream(cmd: Sequence[str]) -> Tuple[int, str]:
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    output_lines: List[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        output_lines.append(line)
        print(line, end="")
    return_code = process.wait()
    return return_code, "".join(output_lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Select cross-seed releases and upload through Upload Assistant")
    parser.add_argument("--qbit-url", default="http://127.0.0.1:8080", help="qBittorrent Web API base URL")
    parser.add_argument("--tracker", help="Target tracker code (e.g. ANT)")
    parser.add_argument("--media", choices=["movie", "tv", "both"], help="Media scope")
    parser.add_argument("--select", help="Selection indexes (e.g. 1,3-5 or all)")
    parser.add_argument("--limit", type=int, default=200, help="How many candidates to display (0 for all)")
    parser.add_argument("--dry-run", action="store_true", help="Print Upload Assistant commands without executing")
    parser.add_argument("--include-upload-tagged", action="store_true", help="Include torrents already tagged 'upload'")
    parser.add_argument("--report", help="Write candidate/report JSON to this path")

    parser.add_argument("--ua-container", default="upload-assistant-cli", help="Upload Assistant container name")
    parser.add_argument("--ua-python", default="/venv/bin/python", help="Python binary inside Upload Assistant container")
    parser.add_argument("--ua-script", default="/Upload-Assistant/upload.py", help="Upload Assistant script path")
    parser.add_argument("--ua-client", default="qbit-main", help="Upload Assistant client name")
    parser.add_argument("--ua-tag", default="upload", help="qBittorrent tag applied by Upload Assistant")
    parser.add_argument(
        "--ua-category",
        default="cross-seed",
        help="qBittorrent category applied by Upload Assistant (recommended: cross-seed)",
    )
    parser.add_argument(
        "--ua-interactive",
        action="store_true",
        help="Do not pass unattended flags to Upload Assistant",
    )
    parser.add_argument("--ua-extra-args", help="Extra arguments forwarded to Upload Assistant")

    args = parser.parse_args()

    qbit = QBitAPI(args.qbit_url)

    try:
        cross_seed = qbit.get_torrents("cross-seed")
        movies = qbit.get_torrents("movies")
        tvshows = qbit.get_torrents("tvshows")
    except Exception as exc:
        print(f"Failed to query qBittorrent API: {exc}", file=sys.stderr)
        return 1

    configured_trackers = get_ua_configured_trackers(args.ua_container, args.ua_python)
    tracker_code = prompt_tracker_code(configured_trackers, args.tracker)
    media_scope = prompt_media_scope(args.media)

    tracker_patterns = resolve_tracker_patterns(args.ua_container, args.ua_python, tracker_code)
    if not tracker_patterns:
        print(
            f"Could not resolve tracker host patterns for {tracker_code}.\n"
            "Add fallback patterns in the script and retry.",
            file=sys.stderr,
        )
        return 1

    print(f"\nTarget tracker: {tracker_code}")
    print(f"Tracker match patterns: {', '.join(tracker_patterns)}")
    print(f"Media scope: {media_scope}")

    movie_keys = {torrent_key(t) for t in movies}
    tv_keys = {torrent_key(t) for t in tvshows}

    exclusion_cats = categories_for_exclusion(media_scope)
    torrents_by_category = {
        "cross-seed": cross_seed,
        "movies": movies,
        "tvshows": tvshows,
    }

    target_existing_keys: Set[Tuple[str, int]] = set()
    for category in exclusion_cats:
        for torrent in torrents_by_category.get(category, []):
            hosts = qbit.get_tracker_hosts(torrent)
            if hosts_match_tracker(hosts, tracker_patterns):
                target_existing_keys.add(torrent_key(torrent))

    excluded_stats = {
        "already_on_target_cross_seed": 0,
        "already_on_target_other_category": 0,
        "outside_media_scope": 0,
        "already_tagged_upload": 0,
    }
    deduped_count = 0

    unique_candidates: Dict[Tuple[str, int], Candidate] = {}
    for torrent in cross_seed:
        hosts = qbit.get_tracker_hosts(torrent)
        key = torrent_key(torrent)
        media_type = classify_media(torrent, movie_keys, tv_keys)

        if not media_in_scope(media_type, media_scope):
            excluded_stats["outside_media_scope"] += 1
            continue

        if hosts_match_tracker(hosts, tracker_patterns):
            excluded_stats["already_on_target_cross_seed"] += 1
            continue

        if key in target_existing_keys:
            excluded_stats["already_on_target_other_category"] += 1
            continue

        tags = split_tags(torrent.get("tags", ""))
        if not args.include_upload_tagged and any(tag.lower() == "upload" for tag in tags):
            excluded_stats["already_tagged_upload"] += 1
            continue

        source_hosts = sorted(hosts) if hosts else ["<unknown>"]
        if key in unique_candidates:
            deduped_count += 1
            existing = unique_candidates[key]
            merged_hosts = sorted(set(existing.source_hosts + source_hosts))
            existing.source_hosts = merged_hosts
            existing.tags = sorted(set(existing.tags + tags), key=str.casefold)
            continue

        unique_candidates[key] = Candidate(
            index=0,
            torrent_hash=torrent.get("hash", ""),
            name=torrent.get("name", ""),
            media_type=media_type,
            size_bytes=int(torrent.get("size", 0) or 0),
            source_hosts=source_hosts,
            content_path=torrent.get("content_path", ""),
            tags=tags,
        )

    candidates = list(unique_candidates.values())

    candidates.sort(key=lambda item: (-item.size_bytes, item.name.casefold()))
    for idx, candidate in enumerate(candidates, start=1):
        candidate.index = idx

    print("\nCounts")
    print(f"- cross-seed total: {len(cross_seed)}")
    print(f"- candidates: {len(candidates)}")
    print(f"- duplicates collapsed: {deduped_count}")
    for key, value in excluded_stats.items():
        print(f"- excluded {key}: {value}")

    if args.report:
        report = {
            "tracker": tracker_code,
            "tracker_patterns": tracker_patterns,
            "media_scope": media_scope,
            "stats": {
                "cross_seed_total": len(cross_seed),
                "candidates": len(candidates),
                "duplicates_collapsed": deduped_count,
                **excluded_stats,
            },
            "candidates": [
                {
                    "index": candidate.index,
                    "hash": candidate.torrent_hash,
                    "name": candidate.name,
                    "media_type": candidate.media_type,
                    "size_bytes": candidate.size_bytes,
                    "source_hosts": candidate.source_hosts,
                    "content_path": candidate.content_path,
                    "tags": candidate.tags,
                }
                for candidate in candidates
            ],
        }
        report_dir = os.path.dirname(os.path.abspath(args.report))
        os.makedirs(report_dir, exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"- report written: {args.report}")

    if not candidates:
        print("\nNo candidates found with current filters.")
        return 0

    print_candidates(candidates, args.limit)

    selection_raw = args.select
    if not selection_raw:
        while True:
            value = input("\nSelect releases (e.g. 1,3-5 or all, q to quit): ").strip()
            if value.lower() in {"q", "quit", "exit"}:
                print("Aborted.")
                return 0
            if value:
                selection_raw = value
                break

    try:
        selected_indexes = parse_selection(selection_raw, len(candidates))
    except Exception as exc:
        print(f"Invalid selection: {exc}", file=sys.stderr)
        return 1

    selected = [candidates[idx - 1] for idx in selected_indexes]
    print(f"\nSelected {len(selected)} release(s).")

    if not args.dry_run:
        confirm = input(f"Proceed with upload to {tracker_code}? [y/N]: ").strip().lower()
        if confirm not in {"y", "yes"}:
            print("Cancelled.")
            return 0

    succeeded: List[Candidate] = []
    skipped: List[Tuple[Candidate, str]] = []
    failed: List[Tuple[Candidate, int]] = []

    for pos, candidate in enumerate(selected, start=1):
        cmd = build_upload_command(
            container=args.ua_container,
            python_bin=args.ua_python,
            upload_script=args.ua_script,
            candidate=candidate,
            tracker_code=tracker_code,
            client_name=args.ua_client,
            qbit_tag=args.ua_tag,
            qbit_category=args.ua_category,
            ua_interactive=args.ua_interactive,
            extra_args=args.ua_extra_args,
        )

        print()
        print(f"[{pos}/{len(selected)}] {candidate.name}")
        print(f"$ {shlex.join(cmd)}")

        if args.dry_run:
            succeeded.append(candidate)
            continue

        try:
            return_code, combined_output = run_and_stream(cmd)
        except Exception as exc:
            print(f"[runner error] {exc}", file=sys.stderr)
            failed.append((candidate, -1))
            continue

        tracker_data_error = has_tracker_data_error(combined_output, tracker_code)
        skip_reason = detect_skip_reason(combined_output, tracker_code)

        if return_code == 0 and not tracker_data_error and skip_reason is None:
            succeeded.append(candidate)
        elif skip_reason is not None:
            skipped.append((candidate, skip_reason))
        else:
            failed.append((candidate, return_code))

    print("\nUpload summary")
    print(f"- successful: {len(succeeded)}")
    print(f"- skipped: {len(skipped)}")
    print(f"- failed: {len(failed)}")
    if skipped:
        for candidate, reason in skipped:
            print(f"  - skipped ({reason}) :: {candidate.name}")
    if failed:
        for candidate, code in failed:
            print(f"  - rc={code} :: {candidate.name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
