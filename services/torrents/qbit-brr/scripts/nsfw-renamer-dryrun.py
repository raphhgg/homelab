#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import argparse
from pathlib import Path
from urllib import request

import yaml

from nsfw_scene_parser import derive_metadata, has_noisy_title_markers, is_weak_title


CONFIG_PATH = Path("/home/raphh/docker/appdata/stash/config/config.yml")
GRAPHQL_URL = "http://127.0.0.1:9999/graphql"
FULL_REPORT = Path("/tmp/nsfw-renamer-dryrun.txt")
SAFE_REPORT = Path("/tmp/nsfw-renamer-dryrun-safe.txt")


def load_api_key() -> str:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return str(config["api_key"])


def gql(api_key: str, query: str) -> dict:
    req = request.Request(
        GRAPHQL_URL,
        data=json.dumps({"query": query}).encode(),
        headers={"Content-Type": "application/json", "ApiKey": api_key},
    )
    with request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode())


def safe_filename_component(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r'[\\/:*?"<>|]+', " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")
    return cleaned


def performer_from_scene(scene: dict, file_path: str) -> str:
    performers = scene.get("performers") or []
    if performers:
        return str(performers[0]["name"])
    return Path(file_path).parts[2]


def preferred_title(scene: dict, parsed_title: str, parsed_confidence: str) -> str:
    scene_title = safe_filename_component(str(scene.get("title") or ""))
    parsed_title = safe_filename_component(parsed_title)
    if parsed_confidence == "high" and parsed_title:
        if not scene_title or is_weak_title(scene_title) or has_noisy_title_markers(scene_title) or "[]" in scene_title:
            return parsed_title
    return scene_title


def preferred_date(scene: dict, parsed_date: str, parsed_confidence: str) -> str:
    scene_date = safe_filename_component(str(scene.get("date") or ""))
    parsed_date = safe_filename_component(parsed_date)
    if parsed_confidence == "high" and parsed_date:
        return parsed_date
    return scene_date


def build_target_name(scene: dict, file_path: str, performer_name: str, parsed_title: str, parsed_date: str, parsed_confidence: str) -> str:
    title = preferred_title(scene, parsed_title, parsed_confidence)
    date = preferred_date(scene, parsed_date, parsed_confidence)
    if date:
        base = f"{performer_name} - {date} - {title}"
    else:
        base = f"{performer_name} - {title}"
    return safe_filename_component(base) + Path(file_path).suffix


def scene_path_filter(performers: list[str]) -> str:
    if not performers:
        return ""
    return " or ".join(f'file_path.startswith("/data/{performer}/")' for performer in performers)


def should_include_scene(file_path: str, performers: list[str]) -> bool:
    if performers:
        return any(file_path.startswith(f"/data/{performer}/") for performer in performers)
    return file_path.startswith("/data/")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate reviewed NSFW rename dry-run reports from Stash scenes.")
    parser.add_argument("--performer", action="append", default=[], help="Limit to a performer. Can be passed multiple times.")
    parser.add_argument("--full-report", type=Path, default=FULL_REPORT)
    parser.add_argument("--safe-report", type=Path, default=SAFE_REPORT)
    args = parser.parse_args()

    api_key = load_api_key()
    query = """
    {
      findScenes(
        filter: { per_page: 500, sort: "id", direction: ASC }
        scene_filter: { path: { modifier: INCLUDES, value: "/data/" } }
      ) {
        scenes {
          id
          title
          date
          files { path }
          performers { name }
        }
      }
    }
    """
    scenes = gql(api_key, query)["data"]["findScenes"]["scenes"]

    all_changes: list[str] = []
    safe_changes: list[str] = []
    safe_count = 0
    skipped_low_confidence = 0

    for scene in scenes:
        files = scene.get("files") or []
        if not files:
            continue
        file_path = str(files[0]["path"])
        if not should_include_scene(file_path, args.performer):
            continue
        performer_name = performer_from_scene(scene, file_path)
        parsed = derive_metadata(file_path, performer_name)

        title = str(scene.get("title") or "").strip()
        if not title:
            continue
        target_name = build_target_name(
            scene,
            file_path,
            performer_name,
            parsed.title,
            parsed.date,
            parsed.confidence,
        )
        target_path = str(Path(file_path).with_name(target_name))
        if target_path == file_path:
            continue

        line = (
            f"[{parsed.family}/{parsed.confidence}/safe={str(parsed.rename_safe).lower()}] "
            f"{file_path} -> {target_path}"
        )
        all_changes.append(line)
        if parsed.rename_safe and parsed.confidence == "high":
            safe_changes.append(line)
            safe_count += 1
        else:
            skipped_low_confidence += 1

    args.full_report.write_text("\n".join(all_changes) + ("\n" if all_changes else ""), encoding="utf-8")
    args.safe_report.write_text("\n".join(safe_changes) + ("\n" if safe_changes else ""), encoding="utf-8")

    print(
        json.dumps(
            {
                "performers": args.performer or "all",
                "full_report": str(args.full_report),
                "safe_report": str(args.safe_report),
                "all_changes": len(all_changes),
                "safe_changes": safe_count,
                "skipped_low_confidence": skipped_low_confidence,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
