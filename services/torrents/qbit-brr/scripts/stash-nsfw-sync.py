#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, request

from nsfw_scene_parser import derive_metadata, is_weak_title


CONFIG_PATH = Path("/stash-config/config.yml")
DEFAULT_STASH_URL = "http://172.24.0.1:9999/graphql"
DEFAULT_STASHDB_ENDPOINT = "https://stashdb.org/graphql"
DEFAULT_STASHBOX_PRECEDENCE = [
    "https://stashdb.org/graphql",
    "https://theporndb.net/graphql",
    "https://fansdb.cc/graphql",
]


def load_api_key() -> str:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"missing Stash config: {CONFIG_PATH}")
    for line in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("api_key:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("api_key not found in Stash config")


def load_stashbox_endpoints() -> list[str]:
    if not CONFIG_PATH.exists():
        return DEFAULT_STASHBOX_PRECEDENCE

    endpoints: list[str] = []
    current_endpoint: str | None = None
    current_name: str | None = None

    for raw_line in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("- apikey:"):
            if current_endpoint:
                endpoints.append(current_endpoint)
            current_endpoint = None
            current_name = None
        elif line.startswith("endpoint:"):
            current_endpoint = line.split(":", 1)[1].strip()
        elif line.startswith("name:"):
            current_name = line.split(":", 1)[1].strip()

    if current_endpoint:
        endpoints.append(current_endpoint)

    # Keep the known high-quality order first, then append any configured extras.
    ordered = [endpoint for endpoint in DEFAULT_STASHBOX_PRECEDENCE if endpoint in endpoints]
    ordered.extend(endpoint for endpoint in endpoints if endpoint not in ordered)
    return ordered or DEFAULT_STASHBOX_PRECEDENCE


class StashClient:
    def __init__(self, graphql_url: str, api_key: str) -> None:
        self.graphql_url = graphql_url
        self.api_key = api_key

    def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        req = request.Request(
            self.graphql_url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "ApiKey": self.api_key,
            },
        )
        try:
            with request.urlopen(req, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"stash request failed: {exc.code} {body}") from exc

        if body.get("errors"):
            raise RuntimeError(f"stash graphql error: {body['errors']}")
        data = body.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("stash graphql response missing data")
        return data


def select_scraped_performer(results: list[dict[str, Any]], performer_name: str) -> dict[str, Any] | None:
    target = performer_name.casefold()
    exact = [item for item in results if str(item.get("name", "")).casefold() == target]
    if exact:
        return exact[0]
    if len(results) == 1:
        return results[0]
    return None


def find_performer_id(client: StashClient, performer_name: str) -> str | None:
    data = client.query(
        """
        query($name: String!) {
          findPerformers(
            performer_filter: { name: { value: $name, modifier: EQUALS } }
            filter: { per_page: 5 }
          ) {
            performers { id name }
          }
        }
        """,
        {"name": performer_name},
    )
    performers = data["findPerformers"]["performers"]
    if not performers:
        return None
    return str(performers[0]["id"])


def normalize_stash_path(raw_path: str, performer_name: str) -> str:
    path = raw_path.rstrip("/")
    if path == f"/data/{performer_name}":
        return path
    if path == f"/data/media/nsfw/{performer_name}":
        return f"/data/{performer_name}"
    if path == f"/mnt/data/media/nsfw/{performer_name}":
        return f"/data/{performer_name}"
    if path.startswith("/data/media/nsfw/"):
        return "/data/" + path.split("/data/media/nsfw/", 1)[1]
    if path.startswith("/mnt/data/media/nsfw/"):
        return "/data/" + path.split("/mnt/data/media/nsfw/", 1)[1]
    return path


def get_performer_tag_ids(client: StashClient, performer_id: str) -> list[str]:
    data = client.query(
        """
        query($id: ID!) {
          findPerformer(id: $id) {
            id
            tags { id }
          }
        }
        """,
        {"id": performer_id},
    )
    performer = data.get("findPerformer") or {}
    tags = performer.get("tags") or []
    return [str(tag["id"]) for tag in tags if isinstance(tag, dict) and tag.get("id")]


def find_tag_id(client: StashClient, tag_name: str) -> str | None:
    data = client.query(
        """
        query($name: String!) {
          findTags(tag_filter: { name: { value: $name, modifier: EQUALS } } filter: { per_page: 5 }) {
            tags { id name }
          }
        }
        """,
        {"name": tag_name},
    )
    tags = data["findTags"]["tags"]
    if not tags:
        return None
    return str(tags[0]["id"])


def create_tag(client: StashClient, tag_name: str) -> str:
    data = client.query(
        """
        mutation($name: String!) {
          tagCreate(input: { name: $name, ignore_auto_tag: true }) {
            id
            name
          }
        }
        """,
        {"name": tag_name},
    )
    return str(data["tagCreate"]["id"])


def ensure_performer_tag(client: StashClient, performer_id: str, performer_name: str) -> str:
    tag_id = find_tag_id(client, performer_name)
    if tag_id is None:
        tag_id = create_tag(client, performer_name)

    existing_tag_ids = get_performer_tag_ids(client, performer_id)
    if tag_id not in existing_tag_ids:
        client.query(
            """
            mutation($id: ID!, $tag_ids: [ID!]) {
              performerUpdate(input: { id: $id, tag_ids: $tag_ids }) {
                id
              }
            }
            """,
            {"id": performer_id, "tag_ids": existing_tag_ids + [tag_id]},
        )
    return tag_id


def create_performer(client: StashClient, performer_name: str) -> str:
    data = client.query(
        """
        mutation($name: String!) {
          performerCreate(input: { name: $name, ignore_auto_tag: false }) {
            id
            name
          }
        }
        """,
        {"name": performer_name},
    )
    return str(data["performerCreate"]["id"])


def scrape_stashbox_performer(client: StashClient, performer_name: str, endpoint: str) -> dict[str, Any] | None:
    data = client.query(
        """
        query($query: String!, $endpoint: String!) {
          scrapeSinglePerformer(
            source: { stash_box_endpoint: $endpoint }
            input: { query: $query }
          ) {
            name
            remote_site_id
            gender
            urls
            birthdate
            ethnicity
            country
            eye_color
            hair_color
            height
            measurements
            fake_tits
            career_start
            career_end
            tattoos
            piercings
            details
            death_date
            weight
            aliases
            images
          }
        }
        """,
        {"query": performer_name, "endpoint": endpoint},
    )
    results = data.get("scrapeSinglePerformer") or []
    if not isinstance(results, list):
        return None
    selected = select_scraped_performer([item for item in results if isinstance(item, dict)], performer_name)
    if selected:
        selected["_endpoint"] = endpoint
    return selected


def scrape_performer_metadata(client: StashClient, performer_name: str) -> dict[str, Any] | None:
    merged: dict[str, Any] = {}
    stash_ids: list[dict[str, str]] = []

    for endpoint in load_stashbox_endpoints():
        scraped = scrape_stashbox_performer(client, performer_name, endpoint)
        if not scraped:
            continue

        remote_site_id = scraped.get("remote_site_id")
        if remote_site_id:
            stash_ids.append({"endpoint": endpoint, "stash_id": str(remote_site_id)})

        for key, value in scraped.items():
            if key.startswith("_") or key == "remote_site_id":
                continue
            if value in (None, "", [], {}):
                continue
            if key not in merged or merged.get(key) in (None, "", [], {}):
                merged[key] = value

    if not merged and not stash_ids:
        return
    merged["stash_ids"] = stash_ids
    return merged


def parse_height(value: Any) -> int | None:
    if value in (None, ""):
        return None
    match = re.search(r"\d+", str(value))
    if not match:
        return None
    return int(match.group(0))


def parse_weight(value: Any) -> int | None:
    if value in (None, ""):
        return None
    match = re.search(r"\d+", str(value))
    if not match:
        return None
    return int(match.group(0))


def performer_update_mutation(client: StashClient, performer_id: str, performer_name: str, scraped: dict[str, Any] | None) -> None:
    if not scraped:
        return

    alias_string = scraped.get("aliases")
    aliases = [alias.strip() for alias in str(alias_string or "").split(",") if alias.strip()]
    image_url = None
    images = scraped.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, str) and first.strip():
            image_url = first.strip()

    input_data: dict[str, Any] = {"id": performer_id}

    stash_ids = scraped.get("stash_ids")
    if isinstance(stash_ids, list) and stash_ids:
        input_data["stash_ids"] = stash_ids
    if aliases:
        input_data["alias_list"] = aliases
    if image_url:
        input_data["image"] = image_url

    gender = scraped.get("gender")
    if isinstance(gender, str) and gender:
        input_data["gender"] = gender

    direct_string_fields = {
        "disambiguation": "disambiguation",
        "birthdate": "birthdate",
        "ethnicity": "ethnicity",
        "country": "country",
        "eye_color": "eye_color",
        "hair_color": "hair_color",
        "measurements": "measurements",
        "fake_tits": "fake_tits",
        "career_start": "career_start",
        "career_end": "career_end",
        "tattoos": "tattoos",
        "piercings": "piercings",
        "details": "details",
        "death_date": "death_date",
    }
    for scraped_key, input_key in direct_string_fields.items():
        value = scraped.get(scraped_key)
        if isinstance(value, str) and value.strip():
            input_data[input_key] = value.strip()

    urls = scraped.get("urls")
    if isinstance(urls, list) and urls:
        clean_urls = [str(url).strip() for url in urls if str(url).strip()]
        if clean_urls:
            input_data["urls"] = clean_urls

    height = parse_height(scraped.get("height"))
    if height:
        input_data["height_cm"] = height

    weight = parse_weight(scraped.get("weight"))
    if weight:
        input_data["weight"] = weight

    client.query(
        """
        mutation($input: PerformerUpdateInput!) {
          performerUpdate(input: $input) {
            id
          }
        }
        """,
        {"input": input_data},
    )


def run_metadata_scan(client: StashClient, performer_path: str) -> str:
    data = client.query(
        """
        mutation($path: String!) {
          metadataScan(
            input: {
              paths: [$path],
              rescan: true,
              scanGenerateCovers: false,
              scanGeneratePreviews: false,
              scanGenerateImagePreviews: false,
              scanGenerateSprites: false,
              scanGeneratePhashes: false,
              scanGenerateImagePhashes: false,
              scanGenerateThumbnails: false,
              scanGenerateClipPreviews: false
            }
          )
        }
        """,
        {"path": performer_path},
    )
    return str(data["metadataScan"])


def wait_for_job(client: StashClient, job_id: str, timeout_seconds: int = 180) -> None:
    start = time.time()
    while time.time() - start < timeout_seconds:
        data = client.query(
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
        job = data.get("findJob")
        if job is None:
            return
        status = str(job.get("status", "")).upper()
        if status != "RUNNING":
            return
        time.sleep(2)


def find_scene_ids_for_path(client: StashClient, performer_path: str) -> list[str]:
    page = 1
    scene_ids: list[str] = []
    while True:
        data = client.query(
            """
            query($path: String!, $page: Int!) {
              findScenes(
                scene_filter: { path: { value: $path, modifier: INCLUDES } }
                filter: { per_page: 100, page: $page }
              ) {
                count
                scenes { id }
              }
            }
            """,
            {"path": performer_path, "page": page},
        )
        scenes = data["findScenes"]["scenes"]
        if not scenes:
            break
        scene_ids.extend(str(scene["id"]) for scene in scenes)
        if len(scenes) < 100:
            break
        page += 1
    return scene_ids


def find_scenes_for_path(client: StashClient, performer_path: str) -> list[dict[str, Any]]:
    page = 1
    scenes: list[dict[str, Any]] = []
    while True:
        data = client.query(
            """
            query($path: String!, $page: Int!) {
              findScenes(
                scene_filter: { path: { value: $path, modifier: INCLUDES } }
                filter: { per_page: 100, page: $page }
              ) {
                scenes {
                  id
                  title
                  date
                  details
                  performers { id name }
                  files { path }
                }
              }
            }
            """,
            {"path": performer_path, "page": page},
        )
        batch = data["findScenes"]["scenes"]
        if not batch:
            break
        scenes.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return scenes


def attach_scenes_to_performer(client: StashClient, scene_ids: list[str], performer_id: str) -> None:
    if not scene_ids:
        return
    client.query(
        """
        mutation($ids: [ID!], $performer_id: ID!) {
          bulkSceneUpdate(
            input: {
              ids: $ids,
              performer_ids: { mode: ADD, ids: [$performer_id] },
              organized: true
            }
          ) {
            id
          }
        }
        """,
        {"ids": scene_ids, "performer_id": performer_id},
    )


def dedupe_scene_performers(client: StashClient, performer_path: str, performer_id: str) -> None:
    scene_ids = find_scene_ids_for_path(client, performer_path)
    attach_scenes_to_performer(client, scene_ids, performer_id)


def update_scene_metadata(client: StashClient, scene_id: str, title: str, date: str) -> None:
    client.query(
        """
        mutation($id: ID!, $title: String, $date: String) {
          sceneUpdate(input: { id: $id, title: $title, date: $date }) {
            id
          }
        }
        """,
        {"id": scene_id, "title": title or None, "date": date or None},
    )


def enrich_scene_metadata(client: StashClient, performer_path: str, performer_name: str) -> int:
    updated = 0
    for scene in find_scenes_for_path(client, performer_path):
        title = str(scene.get("title") or "").strip()
        date = str(scene.get("date") or "").strip()
        files = scene.get("files") or []
        if not files:
            continue
        file_path = str(files[0].get("path") or "")
        if not file_path:
            continue

        derived = derive_metadata(file_path, performer_name)
        next_title = title
        if (not next_title or is_weak_title(next_title)) and derived.confidence != "low":
            next_title = derived.title
        next_date = date or derived.date

        if next_title == title and next_date == date:
            continue
        if not next_title and not next_date:
            continue

        update_scene_metadata(client, str(scene["id"]), next_title, next_date)
        updated += 1
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync a performer folder into Stash and enrich the performer from StashDB.")
    parser.add_argument("performer", help="Canonical performer name")
    parser.add_argument("path", help="Stash-visible performer path, e.g. /data/Anna Ralphs")
    parser.add_argument("--stash-url", default=DEFAULT_STASH_URL, help="Stash GraphQL endpoint")
    parser.add_argument("--performer-only", action="store_true", help="Only enrich performer metadata; skip scan and scene updates")
    args = parser.parse_args()

    api_key = load_api_key()
    client = StashClient(args.stash_url, api_key)

    normalized_path = normalize_stash_path(args.path, args.performer)

    performer_id = find_performer_id(client, args.performer)
    if performer_id is None:
        performer_id = create_performer(client, args.performer)

    scraped = scrape_performer_metadata(client, args.performer)
    performer_update_mutation(client, performer_id, args.performer, scraped)
    performer_tag_id = ensure_performer_tag(client, performer_id, args.performer)

    if args.performer_only:
        result = {
            "performer": args.performer,
            "path": normalized_path,
            "performer_id": performer_id,
            "performer_tag_id": performer_tag_id,
            "stashbox_linked": bool(scraped and scraped.get("stash_ids")),
            "performer_only": True,
        }
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")
        return 0

    job_id = run_metadata_scan(client, normalized_path)
    wait_for_job(client, job_id)
    dedupe_scene_performers(client, normalized_path, performer_id)
    updated_scene_metadata = enrich_scene_metadata(client, normalized_path, args.performer)

    result = {
        "performer": args.performer,
        "path": normalized_path,
        "performer_id": performer_id,
        "performer_tag_id": performer_tag_id,
        "stashbox_linked": bool(scraped and scraped.get("stash_ids")),
        "scene_metadata_updated": updated_scene_metadata,
        "scene_count": len(find_scene_ids_for_path(client, normalized_path)),
    }
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
