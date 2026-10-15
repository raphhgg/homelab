#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
import re
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import parse, request


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v", ".ts", ".webm", ".flv"}
TOKEN_RE = re.compile(r"[^a-z0-9]+")
NOISE_WORDS = {
    "1080p",
    "2160p",
    "4k",
    "720p",
    "fullhd",
    "fhd",
    "uhd",
    "mp4",
    "mkv",
    "mov",
    "xxx",
    "com",
}
DEFAULT_TORRENT_ROOT = Path("/mnt/data/torrents/nsfw")
DEFAULT_MEDIA_ROOT = Path("/mnt/data/media/nsfw")
DEFAULT_STASH_DB = Path("/home/raphh/docker/appdata/stash/config/stash-go.sqlite")
DEFAULT_GENERATED_ROOT = Path("/home/raphh/docker/appdata/stash/generated")
DEFAULT_BACKFILL_PERFORMERS = Path("/home/raphh/docker/compose/services/torrents/qbit-brr/scripts/nsfw-backfill-performers.txt")
DEFAULT_REPORT_ROOT = Path("/home/raphh/docker/appdata/nsfw-automation/reports")
DEFAULT_REPORT_JSON = DEFAULT_REPORT_ROOT / "phase2-reconcile/latest/reconcile.json"
DEFAULT_REPORT_MD = DEFAULT_REPORT_ROOT / "phase2-reconcile/latest/reconcile.md"
DEFAULT_QUI_API_KEY_FILE = Path("/home/raphh/docker/appdata/qui/scripts/qui_api_key")


@dataclass(frozen=True)
class VideoFile:
    path: Path
    relative_path: str
    inode: tuple[int, int]
    size: int


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def iter_video_files(root: Path) -> list[VideoFile]:
    if not root.is_dir():
        return []
    files: list[VideoFile] = []
    for path in root.rglob("*"):
        if not path.is_file() or not is_video(path):
            continue
        stat = path.stat()
        files.append(
            VideoFile(
                path=path,
                relative_path=path.relative_to(root).as_posix(),
                inode=(stat.st_dev, stat.st_ino),
                size=stat.st_size,
            )
        )
    return files


def discover_performers(torrent_root: Path, media_root: Path) -> list[str]:
    performers: set[str] = set()
    for root in (torrent_root, media_root):
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if path.is_dir() and path.name.strip():
                performers.add(path.name)
    return sorted(performers, key=str.casefold)


def load_performers_file(path: Path) -> list[str]:
    if not path.is_file():
        return []
    performers: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        performer = line.strip()
        if not performer or performer.startswith("#"):
            continue
        key = performer.casefold()
        if key in seen:
            continue
        seen.add(key)
        performers.append(performer)
    return performers


def http_json(url: str) -> Any:
    with request.urlopen(request.Request(url), timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def http_post_form(url: str, data: dict[str, str]) -> str:
    body = parse.urlencode(data).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8")


def http_post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> str:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with request.urlopen(req, timeout=60) as response:
        return response.read().decode("utf-8")


def fetch_qbit_torrents(qbit_url: str, category: str) -> list[dict[str, Any]]:
    url = f"{qbit_url.rstrip('/')}/api/v2/torrents/info?category={parse.quote(category)}"
    payload = http_json(url)
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def qbit_tags(torrent: dict[str, Any]) -> set[str]:
    tags = torrent.get("tags")
    if isinstance(tags, str):
        return {tag.strip() for tag in tags.split(",") if tag.strip()}
    if isinstance(tags, list):
        return {str(tag).strip() for tag in tags if str(tag).strip()}
    return set()


def qbit_add_tag(qbit_url: str, hashes: list[str], tag: str) -> None:
    if not hashes:
        return
    http_post_form(
        f"{qbit_url.rstrip('/')}/api/v2/torrents/addTags",
        {"hashes": "|".join(hashes), "tags": tag},
    )


def qbit_remove_tag(qbit_url: str, hashes: list[str], tag: str) -> None:
    if not hashes:
        return
    http_post_form(
        f"{qbit_url.rstrip('/')}/api/v2/torrents/removeTags",
        {"hashes": "|".join(hashes), "tags": tag},
    )


def load_qui_api_key(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def qui_bulk_tag_action(qui_url: str, instance_id: int, api_key: str, hashes: list[str], tag: str, action: str) -> None:
    if not hashes:
        return
    http_post_json(
        f"{qui_url.rstrip('/')}/api/instances/{instance_id}/torrents/bulk-action",
        {"action": action, "hashes": hashes, "tags": tag},
        {"X-API-Key": api_key},
    )


def load_stash_api_key() -> str:
    config_path = Path("/home/raphh/docker/appdata/stash/config/config.yml")
    for line in config_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("api_key:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError(f"api_key not found in {config_path}")


def stash_graphql(url: str, api_key: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "ApiKey": api_key},
    )
    with request.urlopen(req, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))
    if body.get("errors"):
        raise RuntimeError(f"stash graphql error: {body['errors']}")
    data = body.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("stash graphql response missing data")
    return data


def stash_job_queue(stash_url: str) -> dict[str, Any]:
    api_key = load_stash_api_key()
    data = stash_graphql(
        stash_url,
        api_key,
        """
        query {
          jobQueue {
            id
            status
            progress
            description
            error
          }
        }
        """,
    )
    jobs = data.get("jobQueue") or []
    active = [
        job
        for job in jobs
        if str(job.get("status") or "").upper() in {"READY", "RUNNING"}
    ]
    return {
        "jobs": jobs,
        "active": active,
        "active_count": len(active),
    }


def performer_qbit_summary(torrents: list[dict[str, Any]], performer: str) -> dict[str, Any]:
    suffix = f"/{performer}"
    matches = [
        torrent
        for torrent in torrents
        if str(torrent.get("save_path", "")).rstrip("/").endswith(suffix)
    ]
    states: dict[str, int] = {}
    for torrent in matches:
        state = str(torrent.get("state") or "unknown")
        states[state] = states.get(state, 0) + 1
    completed = sum(1 for torrent in matches if float(torrent.get("progress") or 0) >= 1)
    return {
        "count": len(matches),
        "completed": completed,
        "states": dict(sorted(states.items())),
    }


def connect_stash(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def stash_performer(conn: sqlite3.Connection, performer: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        select id, name, birthdate, gender, country, ethnicity, eye_color, hair_color,
               height, measurements, fake_tits, career_start, image_blob
          from performers
         where name = ?
        """,
        (performer,),
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    missing = [
        field
        for field in (
            "birthdate",
            "gender",
            "country",
            "ethnicity",
            "eye_color",
            "hair_color",
            "height",
            "measurements",
            "fake_tits",
            "career_start",
            "image_blob",
        )
        if data.get(field) in (None, "")
    ]
    data["missing_fields"] = missing
    data["rich"] = not missing
    data["has_image"] = bool(data.get("image_blob"))
    return data


def stash_scene_rows(conn: sqlite3.Connection, performer: str) -> list[sqlite3.Row]:
    path = f"/data/{performer}"
    return conn.execute(
        """
        select s.id, s.title, s.date, fo.path as folder_path, f.basename, ff.fingerprint
          from scenes s
          join scenes_files sf on sf.scene_id = s.id and sf."primary" = 1
          join files f on f.id = sf.file_id
          join folders fo on fo.id = f.parent_folder_id
          left join files_fingerprints ff on ff.file_id = f.id and ff.type = 'oshash'
         where fo.path = ? or fo.path like ?
         order by s.id
        """,
        (path, f"{path}/%"),
    ).fetchall()


def stash_scene_summary(conn: sqlite3.Connection, performer: str, generated_root: Path) -> dict[str, Any]:
    rows = stash_scene_rows(conn, performer)
    missing_title = 0
    missing_date = 0
    missing_screenshot = 0
    missing_sprite = 0
    missing_preview_samples: list[dict[str, Any]] = []

    screenshots_root = generated_root / "screenshots"
    vtt_root = generated_root / "vtt"

    for row in rows:
        if not str(row["title"] or "").strip():
            missing_title += 1
        if not str(row["date"] or "").strip():
            missing_date += 1

        fingerprint = row["fingerprint"]
        if isinstance(fingerprint, bytes):
            fingerprint = fingerprint.decode("utf-8", errors="ignore")
        fingerprint = str(fingerprint or "").strip()
        if not fingerprint:
            missing_screenshot += 1
            missing_sprite += 1
            continue

        has_screenshot = any((screenshots_root / f"{fingerprint}{suffix}").exists() for suffix in (".webp", ".jpg", ".jpeg", ".png", ".mp4"))
        has_sprite = (vtt_root / f"{fingerprint}_thumbs.vtt").exists() and (vtt_root / f"{fingerprint}_sprite.jpg").exists()
        if not has_screenshot:
            missing_screenshot += 1
        if not has_sprite:
            missing_sprite += 1
        if (not has_screenshot or not has_sprite) and len(missing_preview_samples) < 5:
            missing_preview_samples.append(
                {
                    "scene_id": row["id"],
                    "file": f"{row['folder_path']}/{row['basename']}",
                    "missing_screenshot": not has_screenshot,
                    "missing_sprite": not has_sprite,
                }
            )

    return {
        "count": len(rows),
        "missing_title": missing_title,
        "missing_date": missing_date,
        "missing_screenshot": missing_screenshot,
        "missing_sprite": missing_sprite,
        "missing_preview_samples": missing_preview_samples,
    }


def scene_path_performer(file_path: str, performers: list[str]) -> str | None:
    for performer in performers:
        if file_path == f"/data/{performer}" or file_path.startswith(f"/data/{performer}/"):
            return performer
    return None


def infer_tracker_source(torrent: dict[str, Any]) -> str:
    for key in ("tracker", "comment"):
        value = str(torrent.get(key) or "").casefold()
        if "bitporn" in value:
            return "bitporn"
        if "happyfappy" in value:
            return "happyfappy"
    return "unknown"


def container_data_path_to_host(path: str) -> Path | None:
    if path.startswith("/data/"):
        return Path("/mnt/data") / path[len("/data/") :]
    return None


def qbit_performer(torrent: dict[str, Any], performers: list[str]) -> str | None:
    for key in ("content_path", "save_path"):
        path = str(torrent.get(key) or "").rstrip("/")
        for performer in performers:
            prefix = f"/data/torrents/nsfw/{performer}"
            if path == prefix or path.startswith(f"{prefix}/"):
                return performer
    return None


def media_inode_sets(media_root: Path, performers: list[str]) -> dict[str, set[tuple[int, int]]]:
    return {
        performer: {video.inode for video in iter_video_files(media_root / performer)}
        for performer in performers
    }


def torrent_video_paths_from_qbit(torrent: dict[str, Any]) -> list[Path]:
    content_path = str(torrent.get("content_path") or "")
    host_path = container_data_path_to_host(content_path)
    if host_path is None or not host_path.exists():
        return []
    if host_path.is_file():
        return [host_path] if is_video(host_path) else []
    return [path for path in host_path.rglob("*") if path.is_file() and is_video(path)]


def qbit_no_hardlink_report(
    torrents: list[dict[str, Any]],
    performers: list[str],
    media_root: Path,
    tag: str,
) -> dict[str, Any]:
    media_inodes = media_inode_sets(media_root, performers)
    torrents_report: list[dict[str, Any]] = []
    add_hashes: list[str] = []
    remove_hashes: list[str] = []

    for torrent in torrents:
        performer = qbit_performer(torrent, performers)
        if performer is None:
            continue
        torrent_hash = str(torrent.get("hash") or "")
        if not torrent_hash:
            continue
        video_paths = torrent_video_paths_from_qbit(torrent)
        if not video_paths:
            continue

        linked_paths: list[str] = []
        missing_paths: list[str] = []
        performer_media_inodes = media_inodes.get(performer, set())
        for path in video_paths:
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            relative = path.as_posix().replace("/mnt/data/torrents/nsfw/", "", 1)
            if (stat.st_dev, stat.st_ino) in performer_media_inodes:
                linked_paths.append(relative)
            else:
                missing_paths.append(relative)

        has_hardlink = bool(linked_paths)
        has_tag = tag in qbit_tags(torrent)
        action = "none"
        if not has_hardlink and not has_tag:
            add_hashes.append(torrent_hash)
            action = "add_tag"
        elif has_hardlink and has_tag:
            remove_hashes.append(torrent_hash)
            action = "remove_stale_tag"

        torrents_report.append(
            {
                "hash": torrent_hash,
                "name": torrent.get("name"),
                "performer": performer,
                "source": infer_tracker_source(torrent),
                "save_path": torrent.get("save_path"),
                "content_path": torrent.get("content_path"),
                "tags": sorted(qbit_tags(torrent)),
                "video_count": len(video_paths),
                "hardlinked_video_count": len(linked_paths),
                "missing_hardlink_count": len(missing_paths),
                "has_hardlink": has_hardlink,
                "current_has_tag": has_tag,
                "planned_action": action,
                "missing_samples": missing_paths[:5],
            }
        )

    by_performer: dict[str, dict[str, int]] = {}
    for item in torrents_report:
        performer = str(item["performer"])
        summary = by_performer.setdefault(
            performer,
            {
                "torrents": 0,
                "no_hardlink": 0,
                "has_hardlink": 0,
                "tagged_now": 0,
                "stale_tag": 0,
            },
        )
        summary["torrents"] += 1
        if item["has_hardlink"]:
            summary["has_hardlink"] += 1
        else:
            summary["no_hardlink"] += 1
        if item["planned_action"] == "add_tag":
            summary["tagged_now"] += 1
        elif item["planned_action"] == "remove_stale_tag":
            summary["stale_tag"] += 1

    return {
        "tag": tag,
        "apply": False,
        "total_torrents_checked": len(torrents_report),
        "no_hardlink_count": sum(1 for item in torrents_report if not item["has_hardlink"]),
        "already_tagged_count": sum(1 for item in torrents_report if item["current_has_tag"] and not item["has_hardlink"]),
        "add_tag_count": len(add_hashes),
        "remove_stale_tag_count": len(remove_hashes),
        "add_hashes": add_hashes,
        "remove_hashes": remove_hashes,
        "by_performer": dict(sorted(by_performer.items())),
        "torrents": torrents_report,
    }


def apply_qbit_no_hardlink_tags(qbit_url: str, report: dict[str, Any]) -> dict[str, Any]:
    tag = str(report.get("tag") or "noHL")
    add_hashes = [str(item) for item in report.get("add_hashes") or []]
    remove_hashes = [str(item) for item in report.get("remove_hashes") or []]
    result = {
        "requested": True,
        "tag": tag,
        "added": len(add_hashes),
        "removed_stale": len(remove_hashes),
        "errors": [],
    }
    try:
        qbit_add_tag(qbit_url, add_hashes, tag)
    except Exception as exc:
        result["errors"].append(f"addTags failed: {exc}")
    try:
        qbit_remove_tag(qbit_url, remove_hashes, tag)
    except Exception as exc:
        result["errors"].append(f"removeTags failed: {exc}")
    return result


def apply_qui_no_hardlink_tags(qui_url: str, instance_id: int, api_key_file: Path, report: dict[str, Any]) -> dict[str, Any]:
    tag = str(report.get("tag") or "noHL")
    add_hashes = [str(item) for item in report.get("add_hashes") or []]
    remove_hashes = [str(item) for item in report.get("remove_hashes") or []]
    result = {
        "requested": True,
        "method": "qui_bulk_action",
        "qui_url": qui_url,
        "instance_id": instance_id,
        "tag": tag,
        "added": len(add_hashes),
        "removed_stale": len(remove_hashes),
        "errors": [],
    }
    try:
        api_key = load_qui_api_key(api_key_file)
        qui_bulk_tag_action(qui_url, instance_id, api_key, add_hashes, tag, "addTags")
    except Exception as exc:
        result["errors"].append(f"qui addTags failed: {exc}")
    try:
        api_key = load_qui_api_key(api_key_file)
        qui_bulk_tag_action(qui_url, instance_id, api_key, remove_hashes, tag, "removeTags")
    except Exception as exc:
        result["errors"].append(f"qui removeTags failed: {exc}")
    return result


def scene_path_to_media_host(path: str) -> Path | None:
    if path.startswith("/data/"):
        return Path("/mnt/data/media/nsfw") / path[len("/data/") :]
    return None


def build_torrent_provenance(
    qbit_torrents: list[dict[str, Any]],
    performers: list[str],
) -> dict[tuple[int, int], list[dict[str, Any]]]:
    performer_prefixes = tuple(f"/data/torrents/nsfw/{performer}" for performer in performers)
    provenance: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for torrent in qbit_torrents:
        save_path = str(torrent.get("save_path") or "")
        content_path = str(torrent.get("content_path") or "")
        if not save_path.startswith(performer_prefixes) and not content_path.startswith(performer_prefixes):
            continue
        host_path = container_data_path_to_host(content_path)
        if host_path is None or not host_path.exists():
            continue
        files = [host_path] if host_path.is_file() else [path for path in host_path.rglob("*") if path.is_file() and is_video(path)]
        summary = {
            "torrent_name": torrent.get("name"),
            "hash": torrent.get("hash"),
            "tracker": torrent.get("tracker"),
            "source": infer_tracker_source(torrent),
            "save_path": save_path,
            "content_path": content_path,
            "comment": torrent.get("comment"),
        }
        for file_path in files:
            try:
                stat = file_path.stat()
            except FileNotFoundError:
                continue
            provenance.setdefault((stat.st_dev, stat.st_ino), []).append(summary)
    return provenance


def attach_scene_provenance(scene: dict[str, Any], provenance: dict[tuple[int, int], list[dict[str, Any]]]) -> dict[str, Any]:
    path = str(scene.get("path") or "")
    host_path = scene_path_to_media_host(path)
    scene = dict(scene)
    scene["tracker_sources"] = []
    scene["torrent_provenance"] = []
    if host_path is None or not host_path.exists():
        return scene
    stat = host_path.stat()
    matches = provenance.get((stat.st_dev, stat.st_ino), [])
    scene["torrent_provenance"] = matches
    scene["tracker_sources"] = sorted({str(item.get("source") or "unknown") for item in matches})
    return scene


def attach_group_provenance(group: dict[str, Any], provenance: dict[tuple[int, int], list[dict[str, Any]]]) -> dict[str, Any]:
    scenes = [attach_scene_provenance(scene, provenance) for scene in group.get("scenes", [])]
    enriched = add_duplicate_recommendation(scenes)
    for key, value in group.items():
        if key not in enriched:
            enriched[key] = value
    sources_by_scene = [scene.get("tracker_sources") or ["unknown"] for scene in enriched.get("scenes", [])]
    unique_sources = sorted({source for sources in sources_by_scene for source in sources})
    enriched["tracker_sources"] = unique_sources
    enriched["tracker_relationship"] = "mixed_trackers" if len(unique_sources) > 1 else (unique_sources[0] if unique_sources else "unknown")
    return enriched


def normalize_duplicate_title(value: str, performer: str | None) -> str:
    performer_words = set(TOKEN_RE.split((performer or "").casefold()))
    words = []
    for word in TOKEN_RE.split(value.casefold()):
        if not word or len(word) == 1:
            continue
        if word in performer_words or word in NOISE_WORDS:
            continue
        if word.isdigit():
            continue
        words.append(word)
    return " ".join(words)


def title_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def duplicate_source_rank(scene: dict[str, Any]) -> int:
    sources = set(scene.get("tracker_sources") or [])
    if "happyfappy" in sources:
        return 2
    if "bitporn" in sources:
        return 1
    return 0


def duplicate_keep_key(scene: dict[str, Any]) -> tuple[int, int, int, int, float, str]:
    height = int(scene.get("height") or 0)
    width = int(scene.get("width") or 0)
    size = int(scene.get("size") or 0)
    duration = float(scene.get("duration") or 0)
    path = str(scene.get("path") or "")
    return (height, width, duplicate_source_rank(scene), size, duration, path)


def add_duplicate_recommendation(entries: list[dict[str, Any]]) -> dict[str, Any]:
    if not entries:
        return {"scenes": [], "keep": None, "review_delete": []}
    sorted_entries = sorted(entries, key=duplicate_keep_key, reverse=True)
    keep = sorted_entries[0]
    return {
        "keep": keep,
        "review_delete": sorted_entries[1:],
        "scenes": sorted_entries,
        "recommendation": "keep_highest_resolution_then_happyfappy_then_largest_size",
    }


def stash_native_duplicate_groups(stash_url: str, performers: list[str]) -> dict[str, Any]:
    api_key = load_stash_api_key()
    data = stash_graphql(
        stash_url,
        api_key,
        """
        query {
          findDuplicateScenes {
            id
            title
            files {
              path
              size
              duration
              width
              height
              fingerprints { type value }
            }
            performers { name }
          }
        }
        """,
    )
    groups: list[dict[str, Any]] = []
    for group in data.get("findDuplicateScenes") or []:
        if not isinstance(group, list):
            continue
        entries: list[dict[str, Any]] = []
        for scene in group:
            files = scene.get("files") or []
            file_path = str(files[0].get("path") or "") if files else ""
            performer = scene_path_performer(file_path, performers)
            if not performer:
                continue
            primary_file = files[0] if files else {}
            entries.append(
                {
                    "scene_id": scene.get("id"),
                    "title": scene.get("title"),
                    "performer": performer,
                    "path": file_path,
                    "size": primary_file.get("size"),
                    "duration": primary_file.get("duration"),
                    "width": primary_file.get("width"),
                    "height": primary_file.get("height"),
                    "performers": [item.get("name") for item in scene.get("performers") or []],
                }
            )
        if len(entries) > 1:
            groups.append(add_duplicate_recommendation(entries))
    return {"group_count": len(groups), "groups": groups, "truncated": False}


def add_duplicate_provenance(report: dict[str, Any], provenance: dict[tuple[int, int], list[dict[str, Any]]]) -> dict[str, Any]:
    groups = [attach_group_provenance(group, provenance) for group in report.get("groups", [])]
    tracker_counts: dict[str, int] = {}
    for group in groups:
        relationship = str(group.get("tracker_relationship") or "unknown")
        tracker_counts[relationship] = tracker_counts.get(relationship, 0) + 1
    enriched = dict(report)
    enriched["groups"] = groups
    enriched["tracker_relationship_counts"] = dict(sorted(tracker_counts.items()))
    return enriched


def stash_exact_duplicate_groups(conn: sqlite3.Connection, performers: list[str]) -> dict[str, Any]:
    where_parts = []
    params: list[str] = []
    for performer in performers:
        where_parts.append("(fo.path = ? or fo.path like ?)")
        params.extend([f"/data/{performer}", f"/data/{performer}/%"])
    if not where_parts:
        return {"group_count": 0, "groups": [], "truncated": False}

    rows = conn.execute(
        f"""
        select ff.type, ff.fingerprint, s.id as scene_id, s.title, fo.path as folder_path,
               f.basename, f.size, vf.duration, vf.width, vf.height
          from scenes s
          join scenes_files sf on sf.scene_id = s.id and sf."primary" = 1
          join files f on f.id = sf.file_id
          join folders fo on fo.id = f.parent_folder_id
          join files_fingerprints ff on ff.file_id = f.id and ff.type = 'oshash'
          left join video_files vf on vf.file_id = f.id
         where {" or ".join(where_parts)}
         order by ff.type, ff.fingerprint, s.id
        """,
        params,
    ).fetchall()

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        fingerprint = row["fingerprint"]
        if isinstance(fingerprint, bytes):
            fingerprint = fingerprint.decode("utf-8", errors="ignore")
        key = (str(row["type"]), str(fingerprint))
        file_path = f"{row['folder_path']}/{row['basename']}"
        grouped.setdefault(key, []).append(
            {
                "scene_id": row["scene_id"],
                "title": row["title"],
                "performer": scene_path_performer(file_path, performers),
                "path": file_path,
                "size": row["size"],
                "duration": row["duration"],
                "width": row["width"],
                "height": row["height"],
            }
        )

    duplicate_groups = [
        {"fingerprint_type": key[0], "fingerprint": key[1], "scenes": scenes}
        for key, scenes in grouped.items()
        if len(scenes) > 1
    ]
    duplicate_groups.sort(key=lambda group: len(group["scenes"]), reverse=True)
    return {
        "group_count": len(duplicate_groups),
        "groups": duplicate_groups[:25],
        "truncated": len(duplicate_groups) > 25,
    }


def stash_size_duplicate_candidates(conn: sqlite3.Connection, performers: list[str]) -> dict[str, Any]:
    where_parts = []
    params: list[str] = []
    for performer in performers:
        where_parts.append("(fo.path = ? or fo.path like ?)")
        params.extend([f"/data/{performer}", f"/data/{performer}/%"])
    if not where_parts:
        return {"group_count": 0, "groups": [], "truncated": False}

    rows = conn.execute(
        f"""
        select s.id as scene_id, s.title, fo.path as folder_path,
               f.basename, f.size, vf.duration, vf.width, vf.height
          from scenes s
          join scenes_files sf on sf.scene_id = s.id and sf."primary" = 1
          join files f on f.id = sf.file_id
          join folders fo on fo.id = f.parent_folder_id
          left join video_files vf on vf.file_id = f.id
         where {" or ".join(where_parts)}
         order by f.size, s.id
        """,
        params,
    ).fetchall()

    by_size: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        file_path = f"{row['folder_path']}/{row['basename']}"
        performer = scene_path_performer(file_path, performers)
        normalized = normalize_duplicate_title(str(row["title"] or row["basename"]), performer)
        by_size.setdefault(int(row["size"]), []).append(
            {
                "scene_id": row["scene_id"],
                "title": row["title"],
                "performer": performer,
                "path": file_path,
                "size": row["size"],
                "duration": row["duration"],
                "width": row["width"],
                "height": row["height"],
                "normalized_title": normalized,
            }
        )

    groups: list[dict[str, Any]] = []
    for size, scenes in by_size.items():
        if len(scenes) < 2:
            continue
        max_similarity = 0.0
        for index, left in enumerate(scenes):
            for right in scenes[index + 1 :]:
                max_similarity = max(max_similarity, title_similarity(left["normalized_title"], right["normalized_title"]))
        groups.append(
            {
                "size": size,
                "scene_count": len(scenes),
                "max_title_similarity": round(max_similarity, 3),
                "scenes": scenes,
                "review_reason": "same_file_size",
            }
        )

    groups.sort(key=lambda group: (group["scene_count"], group["max_title_similarity"]), reverse=True)
    return {
        "group_count": len(groups),
        "groups": groups[:25],
        "truncated": len(groups) > 25,
    }


def stash_duplicate_report(
    conn: sqlite3.Connection,
    stash_url: str,
    performers: list[str],
    provenance: dict[tuple[int, int], list[dict[str, Any]]],
) -> dict[str, Any]:
    native: dict[str, Any]
    try:
        native = stash_native_duplicate_groups(stash_url, performers)
    except Exception as exc:
        native = {"error": str(exc), "group_count": "error", "groups": []}
    exact = add_duplicate_provenance(stash_exact_duplicate_groups(conn, performers), provenance)
    size_candidates = add_duplicate_provenance(stash_size_duplicate_candidates(conn, performers), provenance)
    if isinstance(native.get("groups"), list):
        native = add_duplicate_provenance(native, provenance)
    return {
        "native": native,
        "exact_oshash": exact,
        "same_size_candidates": size_candidates,
    }


def scene_ids_missing_generated(conn: sqlite3.Connection, performers: list[str], generated_root: Path) -> list[str]:
    missing: list[str] = []
    screenshots_root = generated_root / "screenshots"
    vtt_root = generated_root / "vtt"
    for performer in performers:
        for row in stash_scene_rows(conn, performer):
            fingerprint = row["fingerprint"]
            if isinstance(fingerprint, bytes):
                fingerprint = fingerprint.decode("utf-8", errors="ignore")
            fingerprint = str(fingerprint or "").strip()
            if not fingerprint:
                missing.append(str(row["id"]))
                continue
            has_sprite = (vtt_root / f"{fingerprint}_thumbs.vtt").exists() and (vtt_root / f"{fingerprint}_sprite.jpg").exists()
            if not has_sprite:
                missing.append(str(row["id"]))
    return missing


def scene_ids_for_performers(conn: sqlite3.Connection, performers: list[str]) -> list[str]:
    scene_ids: list[str] = []
    for performer in performers:
        scene_ids.extend(str(row["id"]) for row in stash_scene_rows(conn, performer))
    return scene_ids


def generate_phashes(
    stash_url: str,
    scene_ids: list[str],
    wait: bool,
    timeout_seconds: int,
    job_queue: dict[str, Any],
    force: bool,
) -> dict[str, Any]:
    if job_queue.get("active_count") and not force:
        return {
            "requested": False,
            "scene_count": len(scene_ids),
            "job_id": None,
            "status": "blocked_active_jobs",
            "active_jobs": job_queue.get("active", []),
        }
    if not scene_ids:
        return {"requested": False, "scene_count": 0, "job_id": None, "status": "no_scenes"}

    api_key = load_stash_api_key()
    data = stash_graphql(
        stash_url,
        api_key,
        """
        mutation($input: GenerateMetadataInput!) {
          metadataGenerate(input: $input)
        }
        """,
        {
            "input": {
                "sceneIDs": scene_ids,
                "covers": False,
                "sprites": False,
                "previews": False,
                "imagePreviews": False,
                "markers": False,
                "markerImagePreviews": False,
                "markerScreenshots": False,
                "transcodes": False,
                "forceTranscodes": False,
                "phashes": True,
                "interactiveHeatmapsSpeeds": False,
                "imagePhashes": False,
                "imageThumbnails": False,
                "clipPreviews": False,
                "overwrite": False,
            }
        },
    )
    job_id = str(data["metadataGenerate"])
    result: dict[str, Any] = {
        "requested": True,
        "scene_count": len(scene_ids),
        "job_id": job_id,
        "status": "queued",
        "waited": False,
    }
    if not wait:
        return result

    start = time.time()
    result["waited"] = True
    while time.time() - start < timeout_seconds:
        job_data = stash_graphql(
            stash_url,
            api_key,
            """
            query($id: ID!) {
              findJob(input: { id: $id }) {
                id
                status
                progress
                error
              }
            }
            """,
            {"id": job_id},
        )
        job = job_data.get("findJob")
        if not job:
            result["status"] = "not_found"
            return result
        result["last_job"] = job
        status = str(job.get("status") or "").upper()
        if status and status != "RUNNING":
            result["status"] = status.lower()
            return result
        time.sleep(5)
    result["status"] = "timeout"
    return result


def generate_previews(
    stash_url: str,
    scene_ids: list[str],
    wait: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    if not scene_ids:
        return {"requested": False, "scene_count": 0, "job_id": None, "status": "nothing_missing"}
    api_key = load_stash_api_key()
    data = stash_graphql(
        stash_url,
        api_key,
        """
        mutation($input: GenerateMetadataInput!) {
          metadataGenerate(input: $input)
        }
        """,
        {
            "input": {
                "sceneIDs": scene_ids,
                "covers": True,
                "sprites": True,
                "previews": True,
                "imagePreviews": False,
                "markers": False,
                "markerImagePreviews": False,
                "markerScreenshots": False,
                "transcodes": False,
                "forceTranscodes": False,
                "phashes": False,
                "interactiveHeatmapsSpeeds": False,
                "imagePhashes": False,
                "imageThumbnails": False,
                "clipPreviews": True,
                "overwrite": False,
            }
        },
    )
    job_id = str(data["metadataGenerate"])
    result: dict[str, Any] = {
        "requested": True,
        "scene_count": len(scene_ids),
        "job_id": job_id,
        "status": "queued",
        "waited": False,
    }
    if not wait:
        return result

    start = time.time()
    result["waited"] = True
    while time.time() - start < timeout_seconds:
        job_data = stash_graphql(
            stash_url,
            api_key,
            """
            query($id: ID!) {
              findJob(input: { id: $id }) {
                id
                status
                progress
                error
              }
            }
            """,
            {"id": job_id},
        )
        job = job_data.get("findJob")
        if not job:
            result["status"] = "not_found"
            return result
        result["last_job"] = job
        status = str(job.get("status") or "").upper()
        if status and status != "RUNNING":
            result["status"] = status.lower()
            return result
        time.sleep(5)
    result["status"] = "timeout"
    return result


def hardlink_summary(torrent_files: list[VideoFile], media_files: list[VideoFile]) -> dict[str, Any]:
    media_inodes = {item.inode for item in media_files}
    linked = [item for item in torrent_files if item.inode in media_inodes]
    missing = [item for item in torrent_files if item.inode not in media_inodes]
    return {
        "torrent_videos": len(torrent_files),
        "media_videos": len(media_files),
        "hardlinked_from_torrents": len(linked),
        "missing_hardlinks": len(missing),
        "missing_samples": [item.relative_path for item in missing[:10]],
    }


def run_command(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(args, text=True, capture_output=True, check=False)
    return {
        "command": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def apply_safe_for_performer(performer: str, torrent_root: Path) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    torrent_path = torrent_root / performer
    if torrent_path.is_dir():
        actions.append(
            run_command(
                [
                    "docker",
                    "exec",
                    "-e",
                    "NSFW_SKIP_STASH_SYNC=1",
                    "qbit-brr",
                    "/scripts/hardlink-nsfw.sh",
                    f"/data/torrents/nsfw/{performer}",
                ]
            )
        )
    actions.append(run_command(["docker", "exec", "qbit-brr", "/scripts/stash-nsfw-sync.py", performer, f"/data/{performer}", "--performer-only"]))
    return actions


def run_qbit_prune_report(performer: str, qbit_url: str, category: str) -> dict[str, Any] | None:
    script = Path("/home/raphh/docker/compose/services/torrents/autobrr/scripts/nsfw_release_select.py")
    if not script.exists():
        return None
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "qbit-prune",
            "--performer",
            performer,
            "--qbit-url",
            qbit_url,
            "--category",
            category,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return {"error": completed.stderr.strip() or completed.stdout.strip()}
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"error": completed.stdout.strip()}
    return {
        "delete_groups": len(payload.get("delete_groups") or []),
        "review_groups": len(payload.get("review_groups") or []),
        "skipped_titles": len(payload.get("skipped_titles") or []),
    }


def run_rename_dryrun(performers: list[str]) -> dict[str, Any] | None:
    return run_rename_dryrun_to(performers, Path("/tmp/nsfw-renamer-dryrun.txt"), Path("/tmp/nsfw-renamer-dryrun-safe.txt"))


def run_rename_dryrun_to(performers: list[str], full_report: Path, safe_report: Path) -> dict[str, Any] | None:
    script = Path("/home/raphh/docker/compose/services/torrents/qbit-brr/scripts/nsfw-renamer-dryrun.py")
    if not script.exists():
        return None
    args = [
        sys.executable,
        str(script),
        "--full-report",
        str(full_report),
        "--safe-report",
        str(safe_report),
    ]
    for performer in performers:
        args.extend(["--performer", performer])
    completed = subprocess.run(args, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        return {"error": completed.stderr.strip() or completed.stdout.strip()}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"error": completed.stdout.strip()}


def missing_metadata_fields(performer: dict[str, Any]) -> list[str]:
    return performer["stash"].get("performer", {}).get("missing_fields") or []


def qbit_duplicate_groups(performer: dict[str, Any]) -> int:
    qbit_prune = performer.get("qbit_prune") or {}
    value = qbit_prune.get("delete_groups", 0)
    return value if isinstance(value, int) else 0


def performer_status(performer: dict[str, Any]) -> str:
    metadata_missing = missing_metadata_fields(performer)
    scenes = performer["stash"]["scenes"]
    hardlinks = performer["hardlinks"]
    if qbit_duplicate_groups(performer) > 0:
        return "Review dupes"
    if performer["stash"].get("performer", {}).get("missing"):
        return "Missing performer"
    if hardlinks["torrent_videos"] > 0 and hardlinks["media_videos"] == 0:
        return "No media"
    if scenes["count"] > 0 and scenes["missing_sprite"] == scenes["count"]:
        return "Needs previews"
    if metadata_missing:
        return "Partial metadata"
    if hardlinks["missing_hardlinks"] > 0:
        return "Check media"
    return "OK"


def metadata_status(performer: dict[str, Any]) -> str:
    stash_performer_data = performer["stash"].get("performer", {})
    if stash_performer_data.get("missing"):
        return "Missing"
    if stash_performer_data.get("rich"):
        return "Rich"
    return f"Partial ({len(missing_metadata_fields(performer))})"


def preview_status(performer: dict[str, Any]) -> str:
    scenes = performer["stash"]["scenes"]
    count = scenes["count"]
    missing = scenes["missing_sprite"]
    if count == 0:
        return "-"
    if missing == 0:
        return "OK"
    return f"{missing}/{count} missing"


def build_summary(report: dict[str, Any]) -> dict[str, Any]:
    performers = report["performers"]
    rename = report.get("rename_dryrun") or {}
    duplicates = report.get("stash_duplicates") or {}
    native_duplicates = duplicates.get("native") or {}
    exact_duplicates = duplicates.get("exact_oshash") or {}
    size_candidates = duplicates.get("same_size_candidates") or {}
    native_duplicate_groups = native_duplicates.get("group_count", 0)
    if not isinstance(native_duplicate_groups, int):
        native_duplicate_groups = 0
    exact_duplicate_groups = exact_duplicates.get("group_count", 0)
    if not isinstance(exact_duplicate_groups, int):
        exact_duplicate_groups = 0
    size_candidate_groups = size_candidates.get("group_count", 0)
    if not isinstance(size_candidate_groups, int):
        size_candidate_groups = 0
    qbit_dupes = sum(qbit_duplicate_groups(performer) for performer in performers)
    no_hardlink_tagging = report.get("qbit_no_hardlink_tagging") or {}
    no_hardlink_torrents = no_hardlink_tagging.get("no_hardlink_count", 0)
    if not isinstance(no_hardlink_torrents, int):
        no_hardlink_torrents = 0
    missing_previews = sum(performer["stash"]["scenes"]["missing_sprite"] for performer in performers)
    active_jobs = (report.get("stash_jobs") or {}).get("active_count", 0)
    metadata_incomplete = sum(1 for performer in performers if missing_metadata_fields(performer))
    no_media = sum(
        1
        for performer in performers
        if performer["hardlinks"]["torrent_videos"] > 0 and performer["hardlinks"]["media_videos"] == 0
    )
    healthy = sum(1 for performer in performers if performer_status(performer) == "OK")
    safe_renames = rename.get("safe_changes", "n/a")
    status = "OK"
    if qbit_dupes or no_media or native_duplicate_groups or exact_duplicate_groups or size_candidate_groups or no_hardlink_torrents:
        status = "ACTION REQUIRED"
    elif active_jobs or missing_previews or metadata_incomplete or (isinstance(safe_renames, int) and safe_renames > 0):
        status = "NEEDS REVIEW"
    return {
        "status": status,
        "healthy": healthy,
        "qbit_duplicate_groups": qbit_dupes,
        "qbit_no_hardlink_torrents": no_hardlink_torrents,
        "stash_native_duplicate_groups": native_duplicate_groups,
        "stash_exact_duplicate_groups": exact_duplicate_groups,
        "stash_same_size_candidate_groups": size_candidate_groups,
        "missing_previews": missing_previews,
        "stash_active_jobs": active_jobs,
        "metadata_incomplete": metadata_incomplete,
        "no_media": no_media,
        "safe_renames": safe_renames,
    }


def build_action_items(report: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    preview_offenders: list[dict[str, Any]] = []
    stash_jobs = report.get("stash_jobs") or {}
    active_jobs = stash_jobs.get("active_count", 0)
    if isinstance(active_jobs, int) and active_jobs:
        items.append(
            {
                "priority": "Medium",
                "area": "Stash jobs",
                "performer": "Stash",
                "issue": f"{active_jobs} active/queued job(s)",
                "next_step": "Wait before queueing pHash generation",
            }
        )
    no_hardlink_tagging = report.get("qbit_no_hardlink_tagging") or {}
    no_hardlink_count = no_hardlink_tagging.get("no_hardlink_count", 0)
    if isinstance(no_hardlink_count, int) and no_hardlink_count:
        items.append(
            {
                "priority": "High",
                "area": "qB noHL",
                "performer": "Allowed library",
                "issue": f"{no_hardlink_count} qB torrent(s) have no media hardlink",
                "next_step": f"Filter tag `{no_hardlink_tagging.get('tag', 'noHL')}` in qui/qB before deleting anything",
            }
        )
    duplicates = report.get("stash_duplicates") or {}
    native_duplicates = duplicates.get("native") or {}
    exact_duplicates = duplicates.get("exact_oshash") or {}
    size_candidates = duplicates.get("same_size_candidates") or {}
    native_duplicate_groups = native_duplicates.get("group_count", 0)
    if isinstance(native_duplicate_groups, int) and native_duplicate_groups:
        items.append(
            {
                "priority": "High",
                "area": "Stash duplicates",
                "performer": "Allowed library",
                "issue": f"{native_duplicate_groups} native pHash duplicate groups",
                "next_step": "Review Stash duplicate groups before deleting anything",
            }
        )
    exact_duplicate_groups = exact_duplicates.get("group_count", 0)
    if isinstance(exact_duplicate_groups, int) and exact_duplicate_groups:
        items.append(
            {
                "priority": "High",
                "area": "Stash duplicates",
                "performer": "Allowed library",
                "issue": f"{exact_duplicate_groups} exact oshash duplicate groups",
                "next_step": "Review Stash duplicate details before deleting anything",
            }
        )
    size_candidate_groups = size_candidates.get("group_count", 0)
    if isinstance(size_candidate_groups, int) and size_candidate_groups:
        items.append(
            {
                "priority": "Medium",
                "area": "Stash duplicates",
                "performer": "Allowed library",
                "issue": f"{size_candidate_groups} same-size duplicate candidate groups",
                "next_step": "Review same-size candidate paths; likely re-encodes will not match exact hash",
            }
        )
    for performer in report["performers"]:
        duplicate_groups = qbit_duplicate_groups(performer)
        if duplicate_groups:
            items.append(
                {
                    "priority": "High",
                    "area": "qB duplicates",
                    "performer": performer["name"],
                    "issue": f"{duplicate_groups} delete candidate groups",
                    "next_step": "Review qbit-prune details before deleting anything",
                }
            )

        scenes = performer["stash"]["scenes"]
        if scenes["count"] and scenes["missing_sprite"]:
            preview_offenders.append(
                {
                    "performer": performer["name"],
                    "missing": scenes["missing_sprite"],
                    "count": scenes["count"],
                }
            )

        missing_fields = missing_metadata_fields(performer)
        if missing_fields:
            priority = "High" if "image_blob" in missing_fields or "gender" in missing_fields else "Medium"
            issue = ", ".join(missing_fields[:4]) + ("..." if len(missing_fields) > 4 else "")
            items.append(
                {
                    "priority": priority,
                    "area": "Metadata",
                    "performer": performer["name"],
                    "issue": issue,
                    "next_step": "Review StashDB match/enrichment",
                }
            )

        hardlinks = performer["hardlinks"]
        if hardlinks["torrent_videos"] > 0 and hardlinks["media_videos"] == 0:
            items.append(
                {
                    "priority": "High",
                    "area": "Media",
                    "performer": performer["name"],
                    "issue": "Torrent videos exist but media has none",
                    "next_step": "Run safe hardlink backfill",
                }
            )
    if preview_offenders:
        total_missing = sum(item["missing"] for item in preview_offenders)
        total_scenes = sum(item["count"] for item in preview_offenders)
        top_offenders = sorted(preview_offenders, key=lambda item: item["missing"], reverse=True)[:5]
        top_text = ", ".join(f"{item['performer']} ({item['missing']})" for item in top_offenders)
        items.append(
            {
                "priority": "High",
                "area": "Previews",
                "performer": "All affected",
                "issue": f"{total_missing}/{total_scenes} missing sprites. Top: {top_text}",
                "next_step": "Run Stash preview/sprite generation",
            }
        )
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    area_order = {"qB duplicates": 0, "qB noHL": 1, "Stash duplicates": 2, "Stash jobs": 3, "Media": 4, "Previews": 5, "Metadata": 6}
    return sorted(
        items,
        key=lambda item: (
            priority_order.get(item["priority"], 9),
            area_order.get(item["area"], 9),
            item["performer"],
        ),
    )


def build_apply_summary(report: dict[str, Any]) -> list[str]:
    if not report["apply_safe"]:
        return []
    lines: list[str] = []
    errors = 0
    for performer in report["performers"]:
        failed = [action for action in performer.get("apply_actions") or [] if action.get("returncode") != 0]
        if failed:
            errors += len(failed)
            lines.append(f"- `{performer['name']}`: {len(failed)} failed safe action(s)")
    if not lines:
        lines.append("- All safe actions completed without command errors.")
    else:
        lines.insert(0, f"- Safe action command errors: `{errors}`")
    return lines


def duplicate_review_plan(report: dict[str, Any]) -> dict[str, Any]:
    native = (report.get("stash_duplicates") or {}).get("native") or {}
    groups = native.get("groups") or []
    performers: dict[str, list[dict[str, Any]]] = {}
    tracker_relationship_counts: dict[str, int] = {}
    for index, group in enumerate(groups, 1):
        keep = group.get("keep") or {}
        review_delete = group.get("review_delete") or []
        performer = str(keep.get("performer") or "Unknown")
        relationship = str(group.get("tracker_relationship") or "unknown")
        tracker_relationship_counts[relationship] = tracker_relationship_counts.get(relationship, 0) + 1
        performers.setdefault(performer, []).append(
            {
                "group": index,
                "relationship": relationship,
                "recommendation": group.get("recommendation"),
                "keep": keep,
                "review_delete": review_delete,
                "delete_count": len(review_delete),
            }
        )

    return {
        "generated_at": report.get("generated_at"),
        "source_report": report.get("output_json"),
        "policy": "keep_highest_resolution_then_happyfappy_then_largest_size",
        "group_count": len(groups),
        "review_delete_count": sum(len(group.get("review_delete") or []) for group in groups),
        "tracker_relationship_counts": dict(sorted(tracker_relationship_counts.items())),
        "performers": dict(sorted(performers.items())),
    }


def build_duplicate_review_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# NSFW Duplicate Cleanup Review",
        "",
        f"Generated: `{plan.get('generated_at')}`",
        f"Source report: `{plan.get('source_report')}`",
        f"Policy: `{plan.get('policy')}`",
        "",
        "## Summary",
        "",
        f"- Duplicate groups: `{plan.get('group_count')}`",
        f"- Review-delete candidates: `{plan.get('review_delete_count')}`",
        f"- Tracker relationships: `{plan.get('tracker_relationship_counts')}`",
        "",
        "## Safety",
        "",
        "- This is a review plan only.",
        "- Do not delete torrent payloads from qBittorrent from this plan.",
        "- Approved cleanup should remove duplicate media hardlinks and Stash scene entries only.",
        "",
    ]

    for performer, groups in (plan.get("performers") or {}).items():
        lines.extend(
            [
                f"## {performer}",
                "",
                "| Group | Relationship | Keep | Review Delete |",
                "| ---: | --- | --- | --- |",
            ]
        )
        for group in groups:
            keep = group.get("keep") or {}
            deletes = group.get("review_delete") or []
            keep_text = "`{path}`<br>{height}p, {size}<br>source: {source}".format(
                path=keep.get("path"),
                height=keep.get("height"),
                size=keep.get("size"),
                source=", ".join(keep.get("tracker_sources") or ["unknown"]),
            )
            delete_text = "<br>".join(
                "`{path}` ({height}p, {size}, source: {source})".format(
                    path=scene.get("path"),
                    height=scene.get("height"),
                    size=scene.get("size"),
                    source=", ".join(scene.get("tracker_sources") or ["unknown"]),
                )
                for scene in deletes
            )
            lines.append(
                "| {group} | {relationship} | {keep} | {delete} |".format(
                    group=group.get("group"),
                    relationship=group.get("relationship"),
                    keep=keep_text,
                    delete=delete_text,
                )
            )
        lines.append("")
    return "\n".join(lines)


def update_latest_link(report_dir: Path) -> None:
    latest = report_dir.parent / "latest"
    if latest.is_symlink() or latest.exists():
        if latest.is_dir() and not latest.is_symlink():
            return
        latest.unlink()
    latest.symlink_to(report_dir.name, target_is_directory=True)


def build_markdown(report: dict[str, Any]) -> str:
    rename = report.get("rename_dryrun") or {}
    summary = build_summary(report)
    action_items = build_action_items(report)
    generated_at = report.get("generated_at", "unknown")
    lines = [
        "# NSFW Library Reconcile",
        "",
        f"Status: **{summary['status']}**",
        f"Generated: `{generated_at}`",
        f"Mode: `{'safe-apply' if report['apply_safe'] else 'report-only'}`",
        "",
        "## Executive Summary",
        "",
        f"- Performers checked: `{len(report['performers'])}`",
        f"- Performers healthy: `{summary['healthy']}`",
        f"- Missing previews/sprites: `{summary['missing_previews']}`",
        f"- Active Stash jobs: `{summary['stash_active_jobs']}`",
        f"- Metadata incomplete: `{summary['metadata_incomplete']}`",
        f"- qB duplicate groups needing review: `{summary['qbit_duplicate_groups']}`",
        f"- qB torrents tagged/eligible as noHL: `{summary['qbit_no_hardlink_torrents']}`",
        f"- Stash native pHash duplicate groups needing review: `{summary['stash_native_duplicate_groups']}`",
        f"- Stash exact duplicate groups needing review: `{summary['stash_exact_duplicate_groups']}`",
        f"- Stash same-size duplicate candidate groups: `{summary['stash_same_size_candidate_groups']}`",
        f"- Safe rename candidates: `{summary['safe_renames']}`",
        "- Missing hardlinks means torrent video files not represented by the same inode in media; this can include lower-quality duplicates intentionally pruned from media.",
        "",
        "## Action Required",
        "",
    ]
    if action_items:
        lines.extend(
            [
                "| Priority | Area | Performer | Issue | Next Step |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for item in action_items[:25]:
            lines.append(
                "| {priority} | {area} | {performer} | {issue} | {next_step} |".format(
                    priority=item["priority"],
                    area=item["area"],
                    performer=item["performer"],
                    issue=item["issue"],
                    next_step=item["next_step"],
                )
            )
        if len(action_items) > 25:
            lines.append("")
            lines.append(f"_Showing first 25 of {len(action_items)} action items. See JSON for full detail._")
    else:
        lines.append("- No action items.")

    apply_summary = build_apply_summary(report)
    if apply_summary:
        lines.extend(["", "## Safe Apply Result", ""])
        lines.extend(apply_summary)

    stash_duplicates = report.get("stash_duplicates") or {}
    if stash_duplicates:
        native = stash_duplicates.get("native") or {}
        exact = stash_duplicates.get("exact_oshash") or {}
        same_size = stash_duplicates.get("same_size_candidates") or {}
        phash_generation = report.get("phash_generation") or {}
        active_jobs = (report.get("stash_jobs") or {}).get("active_count", 0)
        phash_status = str(phash_generation.get("status") or "").lower()
        if phash_status in {"finished", "complete", "completed", "success"}:
            native_trust = "trusted after pHash generation"
        elif native.get("group_count", 0) and active_jobs == 0:
            native_trust = "trusted; pHash duplicate index returned groups and no Stash jobs are active"
        elif phash_generation.get("requested"):
            native_trust = f"not trusted until pHash job completes; current status: {phash_status}"
        else:
            native_trust = "not trusted until pHash generation runs"
        lines.extend(
            [
                "",
                "## Stash Duplicate Review",
                "",
                f"- Native Stash duplicate groups: `{native.get('group_count', 'n/a')}`",
                f"- Native duplicate trust: `{native_trust}`",
                f"- Native tracker relationships: `{native.get('tracker_relationship_counts', {})}`",
                f"- Exact oshash duplicate groups: `{exact.get('group_count', 'n/a')}`",
                f"- Exact tracker relationships: `{exact.get('tracker_relationship_counts', {})}`",
                f"- Same-size candidate groups: `{same_size.get('group_count', 'n/a')}`",
                f"- Same-size tracker relationships: `{same_size.get('tracker_relationship_counts', {})}`",
            ]
        )
        if native.get("error"):
            lines.append(f"- Native duplicate query error: `{native['error']}`")
        native_groups = native.get("groups") or []
        if native_groups:
            lines.extend(
                [
                    "",
                    "### Native pHash Duplicates",
                    "",
                    "| # | Keep Candidate | Review Delete Candidates |",
                    "| ---: | --- | --- |",
                ]
            )
            for index, group in enumerate(native_groups[:25], 1):
                keep = group.get("keep") or {}
                review_delete = group.get("review_delete") or []
                keep_text = "`{path}`<br>{height}p, {size}<br>source: {source}".format(
                    path=keep.get("path"),
                    height=keep.get("height"),
                    size=keep.get("size"),
                    source=", ".join(keep.get("tracker_sources") or ["unknown"]),
                )
                delete_text = "<br>".join(
                    "`{path}` ({height}p, {size}, source: {source})".format(
                        path=scene.get("path"),
                        height=scene.get("height"),
                        size=scene.get("size"),
                        source=", ".join(scene.get("tracker_sources") or ["unknown"]),
                    )
                    for scene in review_delete[:4]
                )
                lines.append(f"| {index} | {keep_text} | {delete_text} |")
            if len(native_groups) > 25:
                lines.append("")
                lines.append(f"_Showing first 25 of {len(native_groups)} native pHash groups. See JSON report for all groups._")
        exact_groups = exact.get("groups") or []
        if exact_groups:
            lines.extend(["", "| Fingerprint | Scenes | Sample Paths |", "| --- | ---: | --- |"])
            for group in exact_groups[:10]:
                paths = "<br>".join(
                    f"`{scene['path']}` ({', '.join(scene.get('tracker_sources') or ['unknown'])})"
                    for scene in group.get("scenes", [])[:3]
                )
                lines.append(
                    "| {fingerprint} | {count} | {paths} |".format(
                        fingerprint=group.get("fingerprint"),
                        count=len(group.get("scenes", [])),
                        paths=paths,
                    )
                )
            if exact.get("truncated"):
                lines.append("")
                lines.append("_Duplicate details truncated. See JSON report for full retained sample._")
        same_size_groups = same_size.get("groups") or []
        if same_size_groups:
            lines.extend(["", "### Same-Size Candidates", "", "| Size | Similarity | Scenes | Sample Paths |", "| ---: | ---: | ---: | --- |"])
            for group in same_size_groups[:12]:
                paths = "<br>".join(
                    f"`{scene['path']}` ({', '.join(scene.get('tracker_sources') or ['unknown'])})"
                    for scene in group.get("scenes", [])[:3]
                )
                lines.append(
                    "| {size} | {similarity} | {count} | {paths} |".format(
                        size=group.get("size"),
                        similarity=group.get("max_title_similarity"),
                        count=group.get("scene_count"),
                        paths=paths,
                    )
                )
            if same_size.get("truncated"):
                lines.append("")
                lines.append("_Same-size candidate details truncated. See JSON report for full retained sample._")

    no_hardlink_tagging = report.get("qbit_no_hardlink_tagging") or {}
    if no_hardlink_tagging:
        apply_result = no_hardlink_tagging.get("apply_result") or {}
        lines.extend(
            [
                "",
                "## qB noHL Tagging",
                "",
                f"- Tag: `{no_hardlink_tagging.get('tag')}`",
                f"- Applied: `{str(no_hardlink_tagging.get('apply')).lower()}`",
                f"- Torrents checked: `{no_hardlink_tagging.get('total_torrents_checked')}`",
                f"- No hardlink torrents: `{no_hardlink_tagging.get('no_hardlink_count')}`",
                f"- Add tag actions: `{no_hardlink_tagging.get('add_tag_count')}`",
                f"- Remove stale tag actions: `{no_hardlink_tagging.get('remove_stale_tag_count')}`",
            ]
        )
        if apply_result:
            lines.append(f"- Apply method: `{apply_result.get('method', 'unknown')}`")
            lines.append(f"- Apply result: `added={apply_result.get('added')}, removed_stale={apply_result.get('removed_stale')}, errors={len(apply_result.get('errors') or [])}`")
        lines.extend(["", "| Performer | Torrents | noHL | Has HL | To Tag | Stale Tag |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
        for performer, summary in (no_hardlink_tagging.get("by_performer") or {}).items():
            lines.append(
                "| {performer} | {torrents} | {no_hardlink} | {has_hardlink} | {tagged_now} | {stale_tag} |".format(
                    performer=performer,
                    torrents=summary.get("torrents"),
                    no_hardlink=summary.get("no_hardlink"),
                    has_hardlink=summary.get("has_hardlink"),
                    tagged_now=summary.get("tagged_now"),
                    stale_tag=summary.get("stale_tag"),
                )
            )

    stash_jobs = report.get("stash_jobs") or {}
    if stash_jobs:
        lines.extend(["", "## Stash Jobs", ""])
        lines.append(f"- Active/queued jobs: `{stash_jobs.get('active_count', 'n/a')}`")
        for job in (stash_jobs.get("active") or [])[:5]:
            lines.append(
                "- `{id}` `{status}` `{progress}` {description}".format(
                    id=job.get("id"),
                    status=job.get("status"),
                    progress=job.get("progress"),
                    description=job.get("description") or "",
                )
            )

    preview_generation = report.get("preview_generation")
    if preview_generation:
        lines.extend(
            [
                "",
                "## Preview Generation",
                "",
                f"- Requested: `{str(preview_generation.get('requested')).lower()}`",
                f"- Scenes targeted: `{preview_generation.get('scene_count')}`",
                f"- Job ID: `{preview_generation.get('job_id')}`",
                f"- Status: `{preview_generation.get('status')}`",
            ]
        )
        if preview_generation.get("last_job", {}).get("error"):
            lines.append(f"- Error: `{preview_generation['last_job']['error']}`")

    phash_generation = report.get("phash_generation")
    if phash_generation:
        lines.extend(
            [
                "",
                "## pHash Generation",
                "",
                f"- Requested: `{str(phash_generation.get('requested')).lower()}`",
                f"- Scenes targeted: `{phash_generation.get('scene_count')}`",
                f"- Job ID: `{phash_generation.get('job_id')}`",
                f"- Status: `{phash_generation.get('status')}`",
            ]
        )
        if phash_generation.get("active_jobs"):
            lines.append("- Blocked by active Stash jobs.")
        if phash_generation.get("last_job", {}).get("error"):
            lines.append(f"- Error: `{phash_generation['last_job']['error']}`")

    lines.extend(
        [
            "",
            "## Performer Health",
            "",
            "| Performer | qB | Media | Stash | Metadata | Previews | Dupes | Status |",
            "| --- | ---: | ---: | ---: | --- | --- | ---: | --- |",
        ]
    )
    for performer in report["performers"]:
        lines.append(
            "| {name} | {qbit} | {media_videos} | {scenes} | {metadata} | {previews} | {qbit_dupes} | {status} |".format(
                name=performer["name"],
                qbit=performer["qbit"]["count"],
                media_videos=performer["hardlinks"]["media_videos"],
                scenes=performer["stash"]["scenes"]["count"],
                metadata=metadata_status(performer),
                previews=preview_status(performer),
                qbit_dupes=qbit_duplicate_groups(performer),
                status=performer_status(performer),
            )
        )

    lines.extend(
        [
            "",
            "## Detailed Inventory",
            "",
            "| Performer | Torrent Videos | Media Videos | Torrent Files Not In Media | Missing Metadata | Missing Screenshots | Missing Sprites |",
            "| --- | ---: | ---: | ---: | --- | ---: | ---: |",
        ]
    )
    for performer in report["performers"]:
        metadata_missing = ", ".join(missing_metadata_fields(performer)) or "-"
        lines.append(
            "| {name} | {torrent_videos} | {media_videos} | {missing_hardlinks} | {metadata} | {missing_screenshot} | {missing_sprite} |".format(
                name=performer["name"],
                torrent_videos=performer["hardlinks"]["torrent_videos"],
                media_videos=performer["hardlinks"]["media_videos"],
                missing_hardlinks=performer["hardlinks"]["missing_hardlinks"],
                metadata=metadata_missing,
                missing_screenshot=performer["stash"]["scenes"]["missing_screenshot"],
                missing_sprite=performer["stash"]["scenes"]["missing_sprite"],
            )
        )

    lines.extend(
        [
            "",
            "## Generated Artifacts",
            "",
            f"- JSON report: `{report.get('output_json', DEFAULT_REPORT_JSON)}`",
            f"- Markdown report: `{report.get('output_md', DEFAULT_REPORT_MD)}`",
            f"- Duplicate review JSON: `{(report.get('duplicate_review') or {}).get('json', 'n/a')}`",
            f"- Duplicate review Markdown: `{(report.get('duplicate_review') or {}).get('markdown', 'n/a')}`",
            f"- Rename safe report: `{rename.get('safe_report', 'n/a')}`",
            f"- Rename full report: `{rename.get('full_report', 'n/a')}`",
            "",
            "## Review Gates",
            "",
            "- File renames are report-only.",
            "- Torrent duplicate deletion is report-only.",
            "- HappyFappy cross-seed cleanup is report-only.",
            "- Ambiguous scene metadata is not overwritten by this reconciler.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report and optionally apply safe NSFW library reconciliation tasks.")
    parser.add_argument("--performer", action="append", default=[], help="Limit to one performer. Can be passed multiple times.")
    parser.add_argument("--torrent-root", type=Path, default=DEFAULT_TORRENT_ROOT)
    parser.add_argument("--media-root", type=Path, default=DEFAULT_MEDIA_ROOT)
    parser.add_argument("--stash-db", type=Path, default=DEFAULT_STASH_DB)
    parser.add_argument("--generated-root", type=Path, default=DEFAULT_GENERATED_ROOT)
    parser.add_argument("--qbit-url", default="http://127.0.0.1:8085")
    parser.add_argument("--category", default="nsfw")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument(
        "--performers-file",
        type=Path,
        default=DEFAULT_BACKFILL_PERFORMERS,
        help="Default performer allowlist. Use --all-discovered to scan every folder.",
    )
    parser.add_argument("--all-discovered", action="store_true", help="Scan every performer folder under torrent/media roots.")
    parser.add_argument("--apply-safe", action="store_true", help="Run hardlink backfill and performer-only Stash enrichment.")
    parser.add_argument("--stash-url", default="http://127.0.0.1:9999/graphql", help="Stash GraphQL URL")
    parser.add_argument("--generate-previews", action="store_true", help="Queue missing covers/sprites/previews for allowed performer scenes.")
    parser.add_argument("--wait-previews", action="store_true", help="Wait for Stash preview generation job to finish.")
    parser.add_argument("--preview-timeout-seconds", type=int, default=21600, help="Maximum wait time when --wait-previews is set.")
    parser.add_argument("--generate-phashes", action="store_true", help="Queue Stash pHash generation for allowed performer scenes.")
    parser.add_argument("--wait-phashes", action="store_true", help="Wait for Stash pHash generation job to finish.")
    parser.add_argument("--phash-timeout-seconds", type=int, default=21600, help="Maximum wait time when --wait-phashes is set.")
    parser.add_argument("--force-phashes", action="store_true", help="Queue pHashes even if Stash has active/queued jobs.")
    parser.add_argument("--tag-no-hardlinks", action="store_true", help="Add qB tag through qui for torrents whose videos have no media hardlink, and remove stale tags.")
    parser.add_argument("--no-hardlink-tag", default="noHL", help="qB tag used by --tag-no-hardlinks.")
    parser.add_argument("--qui-url", default="http://127.0.0.1:7476", help="qui API base URL")
    parser.add_argument("--qui-instance-id", type=int, default=3, help="qui instance id for qbit-brr.")
    parser.add_argument("--qui-api-key-file", type=Path, default=DEFAULT_QUI_API_KEY_FILE)
    parser.add_argument("--tag-no-hardlinks-direct-qbit", action="store_true", help="Fallback/debug: tag directly through qB instead of qui.")
    parser.add_argument("--skip-rename-dryrun", action="store_true")
    parser.add_argument("--skip-qbit-prune-report", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    generated_at = datetime.now(timezone.utc)
    run_id = generated_at.strftime("%Y%m%dT%H%M%SZ")
    report_dir = args.report_root / "phase2-reconcile" / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    output_json = args.output_json or (report_dir / "reconcile.json")
    output_md = args.output_md or (report_dir / "reconcile.md")
    if args.performer:
        performers = args.performer
    elif args.all_discovered:
        performers = discover_performers(args.torrent_root, args.media_root)
    else:
        performers = load_performers_file(args.performers_file)
        if not performers:
            raise SystemExit(f"no performers found in allowlist: {args.performers_file}")
    qbit_torrents = fetch_qbit_torrents(args.qbit_url, args.category)
    torrent_provenance = build_torrent_provenance(qbit_torrents, performers)
    no_hardlink_tagging = qbit_no_hardlink_report(qbit_torrents, performers, args.media_root, args.no_hardlink_tag)
    if args.tag_no_hardlinks:
        no_hardlink_tagging["apply"] = True
        if args.tag_no_hardlinks_direct_qbit:
            no_hardlink_tagging["apply_result"] = apply_qbit_no_hardlink_tags(args.qbit_url, no_hardlink_tagging)
            no_hardlink_tagging["apply_result"]["method"] = "direct_qbit"
        else:
            no_hardlink_tagging["apply_result"] = apply_qui_no_hardlink_tags(
                args.qui_url,
                args.qui_instance_id,
                args.qui_api_key_file,
                no_hardlink_tagging,
            )

    apply_actions: dict[str, list[dict[str, Any]]] = {}
    if args.apply_safe:
        for performer in performers:
            apply_actions[performer] = apply_safe_for_performer(performer, args.torrent_root)

    conn = connect_stash(args.stash_db)
    stash_jobs = stash_job_queue(args.stash_url)
    preview_generation = None
    if args.generate_previews:
        missing_scene_ids = scene_ids_missing_generated(conn, performers, args.generated_root)
        preview_generation = generate_previews(
            args.stash_url,
            missing_scene_ids,
            wait=args.wait_previews,
            timeout_seconds=args.preview_timeout_seconds,
        )
        stash_jobs = stash_job_queue(args.stash_url)
    phash_generation = None
    if args.generate_phashes:
        phash_generation = generate_phashes(
            args.stash_url,
            scene_ids_for_performers(conn, performers),
            wait=args.wait_phashes,
            timeout_seconds=args.phash_timeout_seconds,
            job_queue=stash_jobs,
            force=args.force_phashes,
        )
        stash_jobs = stash_job_queue(args.stash_url)
    stash_duplicates = stash_duplicate_report(conn, args.stash_url, performers, torrent_provenance)

    performer_reports: list[dict[str, Any]] = []
    for performer in performers:
        torrent_files = iter_video_files(args.torrent_root / performer)
        media_files = iter_video_files(args.media_root / performer)
        performer_report: dict[str, Any] = {
            "name": performer,
            "qbit": performer_qbit_summary(qbit_torrents, performer),
            "hardlinks": hardlink_summary(torrent_files, media_files),
            "stash": {
                "performer": stash_performer(conn, performer) or {"missing": True, "missing_fields": ["performer"]},
                "scenes": stash_scene_summary(conn, performer, args.generated_root),
            },
            "apply_actions": apply_actions.get(performer, []),
        }
        if not args.skip_qbit_prune_report:
            performer_report["qbit_prune"] = run_qbit_prune_report(performer, args.qbit_url, args.category)
        performer_reports.append(performer_report)

    rename_dryrun = None if args.skip_rename_dryrun else run_rename_dryrun_to(
        performers,
        report_dir / "renames-full.txt",
        report_dir / "renames-safe.txt",
    )
    report = {
        "apply_safe": args.apply_safe,
        "generated_at": generated_at.isoformat(),
        "report_dir": str(report_dir),
        "performers": performer_reports,
        "rename_dryrun": rename_dryrun,
        "preview_generation": preview_generation,
        "phash_generation": phash_generation,
        "stash_jobs": stash_jobs,
        "stash_duplicates": stash_duplicates,
        "qbit_no_hardlink_tagging": no_hardlink_tagging,
        "output_json": str(output_json),
        "output_md": str(output_md),
    }
    duplicate_plan = duplicate_review_plan(report)
    duplicate_json = report_dir / "duplicates-review.json"
    duplicate_md = report_dir / "duplicates-review.md"
    report["duplicate_review"] = {
        "json": str(duplicate_json),
        "markdown": str(duplicate_md),
        "group_count": duplicate_plan["group_count"],
        "review_delete_count": duplicate_plan["review_delete_count"],
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(build_markdown(report), encoding="utf-8")
    duplicate_json.write_text(json.dumps(duplicate_plan, indent=2) + "\n", encoding="utf-8")
    duplicate_md.write_text(build_duplicate_review_markdown(duplicate_plan), encoding="utf-8")
    update_latest_link(report_dir)
    print(json.dumps({"json": str(output_json), "markdown": str(output_md), "report_dir": str(report_dir), "performers": len(performer_reports)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
