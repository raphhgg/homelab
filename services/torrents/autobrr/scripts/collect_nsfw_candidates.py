#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib import parse, request


USER_AGENT = "Mozilla/5.0 (compatible; Codex collector)"
DEFAULT_REPORT_ROOT = Path("/home/raphh/docker/appdata/nsfw-automation/reports")
HAPPYFAPPY_ENTRY_RE = re.compile(
    r'href="(?P<download>/torrents\.php\?action=download&amp;id=\d+[^"]*)"[^>]*>.*?'
    r'<a href="(?P<details>/torrents\.php\?id=\d+)"[^>]*>(?P<title>[^<]+)</a>',
    re.IGNORECASE | re.DOTALL,
)
BITPORN_ENTRY_RE = re.compile(
    r'<a class="torrent-search--list__name[^"]*"[^>]*href="(?P<details>https://bitporn\.eu/torrents/(?P<id>\d+))"[^>]*>'
    r'(?P<title>.*?)</a>.*?'
    r'<a[^>]*href="(?P<download>https://bitporn\.eu/torrents/download/\d+)"[^>]*title="Letöltés"[^>]*>.*?</a>.*?'
    r'<td class="torrent-search--list__size">\s*<span>(?P<size>.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)


def make_request(url: str, headers: dict[str, str] | None = None) -> request.Request:
    merged = {"User-Agent": USER_AGENT}
    if headers:
        merged.update(headers)
    return request.Request(url, headers=merged)


def get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    with request.urlopen(make_request(url, headers=headers), timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_text(url: str, headers: dict[str, str] | None = None) -> str:
    with request.urlopen(make_request(url, headers=headers), timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def collect_bitporn(query: str, api_key: str, max_pages: int) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {api_key}"}
    next_url = f"https://bitporn.eu/api/torrents/filter?name={parse.quote(query)}"
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    pages = 0

    while next_url and pages < max_pages:
        payload = get_json(next_url, headers=headers)
        pages += 1

        for item in payload.get("data", []):
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id", ""))
            attrs = item.get("attributes", {})
            if not item_id or not isinstance(attrs, dict) or item_id in seen_ids:
                continue
            seen_ids.add(item_id)

            files = attrs.get("files")
            primary_file = files[0] if isinstance(files, list) and files and isinstance(files[0], dict) else {}

            results.append(
                {
                    "source": "bitporn",
                    "id": item_id,
                    "title": attrs.get("name"),
                    "details_url": attrs.get("details_link"),
                    "download_url": attrs.get("download_link"),
                    "size": attrs.get("size"),
                    "file_name": primary_file.get("name"),
                    "resolution": attrs.get("resolution"),
                }
            )

        links = payload.get("links", {})
        next_url = links.get("next") if isinstance(links, dict) else None

    return results


def collect_bitporn_web(query: str, session_cookie: str, max_pages: int) -> list[dict[str, Any]]:
    headers = {"Cookie": f"bitporn_session={session_cookie}"}
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for page in range(1, max_pages + 1):
        # BitPorn's `name` query param yields much more accurate performer matches
        # than the generic `search` param for this workflow.
        params = {"name": query}
        if page > 1:
            params["page"] = str(page)
        url = f"https://bitporn.eu/torrents?{parse.urlencode(params)}"
        text = get_text(url, headers=headers)
        matches = list(BITPORN_ENTRY_RE.finditer(text))
        if not matches:
            break

        page_added = 0
        for match in matches:
            item_id = match.group("id")
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            page_added += 1
            results.append(
                {
                    "source": "bitporn",
                    "id": item_id,
                    "title": html.unescape(re.sub(r"\s+", " ", match.group("title"))).strip(),
                    "details_url": match.group("details"),
                    "download_url": match.group("download"),
                    "size": html.unescape(match.group("size")).strip(),
                }
            )

        if page_added == 0:
            break

    return results


def collect_happyfappy(query: str, sid: str, max_pages: int) -> list[dict[str, Any]]:
    headers = {"Cookie": f"sid={sid}"}
    results: list[dict[str, Any]] = []
    seen_downloads: set[str] = set()

    for page in range(1, max_pages + 1):
        params = {"searchtext": query}
        if page > 1:
            params["page"] = str(page)
        url = f"https://www.happyfappy.net/torrents.php?{parse.urlencode(params)}"
        text = get_text(url, headers=headers)
        matches = list(HAPPYFAPPY_ENTRY_RE.finditer(text))
        if not matches:
            break

        page_added = 0
        for match in matches:
            download_url = html.unescape(match.group("download"))
            details_url = html.unescape(match.group("details"))
            title = html.unescape(match.group("title")).strip()
            absolute_download = parse.urljoin("https://www.happyfappy.net", download_url)
            absolute_details = parse.urljoin("https://www.happyfappy.net", details_url)
            if absolute_download in seen_downloads:
                continue
            seen_downloads.add(absolute_download)
            page_added += 1
            results.append(
                {
                    "source": "happyfappy",
                    "title": title,
                    "details_url": absolute_details,
                    "download_url": absolute_download,
                }
            )

        if page_added == 0:
            break

    return results


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect BitPorn and HappyFappy release candidates into one JSON file."
    )
    parser.add_argument("--query", required=True, help="Performer or search query")
    parser.add_argument("--bitporn-api-key", help="BitPorn API key")
    parser.add_argument("--bitporn-session", help="BitPorn bitporn_session cookie value")
    parser.add_argument("--happyfappy-sid", help="HappyFappy sid cookie value")
    parser.add_argument("--bitporn-pages", type=int, default=5, help="Maximum BitPorn pages to fetch")
    parser.add_argument("--happyfappy-pages", type=int, default=5, help="Maximum HappyFappy pages to fetch")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    args = parser.parse_args()
    generated_at = datetime.now(timezone.utc)
    run_id = generated_at.strftime("%Y%m%dT%H%M%SZ")
    output_path = args.output or (
        args.report_root
        / "phase1-add-performer"
        / slugify(args.query)
        / run_id
        / "candidates.json"
    )

    results: list[dict[str, Any]] = []
    if args.bitporn_api_key:
        try:
            results.extend(collect_bitporn(args.query, args.bitporn_api_key, args.bitporn_pages))
        except Exception:
            if not args.bitporn_session:
                raise
            results.extend(collect_bitporn_web(args.query, args.bitporn_session, args.bitporn_pages))
    elif args.bitporn_session:
        results.extend(collect_bitporn_web(args.query, args.bitporn_session, args.bitporn_pages))
    if args.happyfappy_sid:
        results.extend(collect_happyfappy(args.query, args.happyfappy_sid, args.happyfappy_pages))

    payload = {
        "query": args.query,
        "generated_at": generated_at.isoformat(),
        "output": str(output_path),
        "results": results,
    }
    output = json.dumps(payload, indent=2)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")
        print(json.dumps({"query": args.query, "json": str(output_path), "results": len(results)}, indent=2))
    else:
        sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
