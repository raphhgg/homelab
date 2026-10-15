#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib import request


DEFAULT_PLAN = Path("/home/raphh/docker/appdata/nsfw-automation/reports/phase2-reconcile/latest/duplicates-review.json")
DEFAULT_MEDIA_ROOT = Path("/mnt/data/media/nsfw")
DEFAULT_STASH_CONFIG = Path("/home/raphh/docker/appdata/stash/config/config.yml")


def load_stash_api_key(config_path: Path) -> str:
    for line in config_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("api_key:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError(f"api_key not found in {config_path}")


def stash_graphql(url: str, api_key: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
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


def scene_path_to_host(path: str, media_root: Path) -> Path:
    if not path.startswith("/data/"):
        raise ValueError(f"scene path is not under /data: {path}")
    return media_root / path[len("/data/") :]


def safe_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def remove_empty_parents(path: Path, stop: Path) -> list[str]:
    removed: list[str] = []
    current = path.parent
    while current != stop and stop in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        removed.append(safe_relative(current, stop))
        current = current.parent
    return removed


def iter_delete_candidates(plan: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_scene_ids: set[str] = set()
    for performer, groups in (plan.get("performers") or {}).items():
        for group in groups:
            for scene in group.get("review_delete") or []:
                scene_id = str(scene.get("scene_id") or "")
                if not scene_id or scene_id in seen_scene_ids:
                    continue
                seen_scene_ids.add(scene_id)
                candidates.append(
                    {
                        "performer": performer,
                        "group": group.get("group"),
                        "relationship": group.get("relationship"),
                        "scene_id": scene_id,
                        "title": scene.get("title"),
                        "path": scene.get("path"),
                        "height": scene.get("height"),
                        "size": scene.get("size"),
                        "tracker_sources": scene.get("tracker_sources") or [],
                    }
                )
    return candidates


def destroy_stash_scene(stash_url: str, api_key: str, scene_id: str, delete_generated: bool) -> None:
    stash_graphql(
        stash_url,
        api_key,
        """
        mutation($input: SceneDestroyInput!) {
          sceneDestroy(input: $input)
        }
        """,
        {
            "input": {
                "id": scene_id,
                "delete_file": False,
                "delete_generated": delete_generated,
                "destroy_file_entry": True,
            }
        },
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safely remove reviewed NSFW duplicate media hardlinks and Stash scenes.")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--media-root", type=Path, default=DEFAULT_MEDIA_ROOT)
    parser.add_argument("--stash-url", default="http://127.0.0.1:9999/graphql")
    parser.add_argument("--stash-config", type=Path, default=DEFAULT_STASH_CONFIG)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--apply", action="store_true", help="Actually delete media hardlinks and Stash scene entries.")
    parser.add_argument("--delete-generated", action="store_true", help="Also remove generated Stash assets for destroyed scenes.")
    parser.add_argument("--allow-single-link", action="store_true", help="Allow deleting media files with link count < 2.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    candidates = iter_delete_candidates(plan)
    actions: list[dict[str, Any]] = []
    api_key = load_stash_api_key(args.stash_config) if args.apply else ""

    for candidate in candidates:
        action = dict(candidate)
        try:
            host_path = scene_path_to_host(str(candidate["path"]), args.media_root).resolve()
            media_root = args.media_root.resolve()
            host_path.relative_to(media_root)
        except Exception as exc:
            action.update({"status": "skipped", "reason": f"unsafe_path: {exc}"})
            actions.append(action)
            continue

        action["host_path"] = str(host_path)
        if not host_path.exists():
            action.update({"status": "skipped", "reason": "file_missing"})
            actions.append(action)
            continue
        if not host_path.is_file():
            action.update({"status": "skipped", "reason": "not_file"})
            actions.append(action)
            continue

        stat = host_path.stat()
        action["link_count"] = stat.st_nlink
        action["actual_size"] = stat.st_size
        if stat.st_nlink < 2 and not args.allow_single_link:
            action.update({"status": "skipped", "reason": "single_link_file"})
            actions.append(action)
            continue

        if not args.apply:
            action.update({"status": "would_delete"})
            actions.append(action)
            continue

        host_path.unlink()
        removed_dirs = remove_empty_parents(host_path, args.media_root.resolve() / str(candidate["performer"]))
        destroy_stash_scene(args.stash_url, api_key, str(candidate["scene_id"]), args.delete_generated)
        action.update({"status": "deleted", "removed_empty_dirs": removed_dirs})
        actions.append(action)

    summary: dict[str, Any] = {
        "apply": args.apply,
        "source_plan": str(args.plan),
        "candidate_count": len(candidates),
        "deleted_count": sum(1 for action in actions if action["status"] == "deleted"),
        "would_delete_count": sum(1 for action in actions if action["status"] == "would_delete"),
        "skipped_count": sum(1 for action in actions if action["status"] == "skipped"),
        "skip_reasons": {},
        "actions": actions,
    }
    for action in actions:
        if action["status"] != "skipped":
            continue
        reason = str(action.get("reason") or "unknown")
        summary["skip_reasons"][reason] = summary["skip_reasons"].get(reason, 0) + 1

    output = json.dumps(summary, indent=2) + "\n"
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(output, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
