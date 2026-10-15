import os
import re
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict

import requests
import yaml


RSS_URL = os.environ.get("LETTERBOXD_RSS_URL", "https://letterboxd.com/raphh11/rss/")
KOMETA_CONFIG_PATH = os.environ.get("KOMETA_CONFIG_PATH", "/config/config.yml")
SYNC_INTERVAL_MINUTES = int(os.environ.get("SYNC_INTERVAL_MINUTES", "30"))
REQUEST_HEADERS = {"User-Agent": "curl/8.5.0", "Accept": "application/json"}
RATING_MAP = {
    "5.0": 10,
    "4.5": 9,
    "4.0": 8,
    "3.5": 7,
    "3.0": 6,
    "2.5": 5,
    "2.0": 4,
    "1.5": 3,
    "1.0": 2,
    "0.5": 1,
}
LIGHT_PUNCT_RE = re.compile(r"['.,!?]")
LEADING_ARTICLE_RE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)


def load_plex_config():
    with open(KOMETA_CONFIG_PATH, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    url = os.environ.get("PLEX_URL") or config["plex"]["url"]
    token = os.environ.get("PLEX_TOKEN") or config["plex"]["token"]
    return url, token


RSS_FETCH_ATTEMPTS = int(os.environ.get("RSS_FETCH_ATTEMPTS", "5"))


def _get_rss_with_retry():
    delay = 10
    for attempt in range(1, RSS_FETCH_ATTEMPTS + 1):
        try:
            response = requests.get(
                RSS_URL,
                headers={"User-Agent": REQUEST_HEADERS["User-Agent"]},
                timeout=(10, 45),
            )
            if response.status_code in (429,) or response.status_code >= 500:
                raise requests.exceptions.HTTPError(f"HTTP {response.status_code}", response=response)
            response.raise_for_status()
            return response
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.HTTPError) as exc:
            if attempt >= RSS_FETCH_ATTEMPTS:
                raise
            print(f"RSS fetch attempt {attempt}/{RSS_FETCH_ATTEMPTS} failed: {type(exc).__name__}: {exc}; retrying in {delay}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 300)


def fetch_rss_items():
    response = _get_rss_with_retry()
    root = ET.fromstring(response.text)
    latest_by_tmdb = OrderedDict()
    for item in root.findall("./channel/item"):
        tmdb_id = item.findtext("{https://themoviedb.org}movieId")
        rating = item.findtext("{https://letterboxd.com}memberRating")
        title = item.findtext("{https://letterboxd.com}filmTitle")
        year = item.findtext("{https://letterboxd.com}filmYear")
        if not tmdb_id or not rating or rating not in RATING_MAP or not title:
            continue
        latest_by_tmdb[tmdb_id] = {
            "title": title,
            "year": int(year) if year else None,
            "plex_rating": RATING_MAP[rating],
        }
    return latest_by_tmdb


def get_metadata(session, base_url, token, rating_key):
    response = session.get(
        f"{base_url}/library/metadata/{rating_key}",
        params={"includeGuids": "1", "X-Plex-Token": token},
        headers=REQUEST_HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["MediaContainer"]["Metadata"][0]


def title_search_queries(title):
    """Variant set before Missing (media-title-normalizer skill).

    1. Exact title
    2. Colon → space
    3. Strip colon (prefer space form first)
    4. Strip light punctuation (' . , ! ?) and collapse spaces
    5. Optional: drop leading The / A / An
    """
    queries = []

    def add(candidate):
        normalized = " ".join(candidate.split())
        if normalized and normalized not in queries:
            queries.append(normalized)

    for candidate in (title, title.replace(":", " "), title.replace(":", "")):
        add(candidate)

    for candidate in list(queries):
        add(LIGHT_PUNCT_RE.sub("", candidate))

    for candidate in list(queries):
        add(LEADING_ARTICLE_RE.sub("", candidate))

    return queries


def build_tmdb_index(session, base_url, token):
    """Map tmdb id -> ratingKey from movie library sections (Guid arrays).

    Prefer id over title string. Plex guid= filter only matches primary plex://
    guids, so we index Guid[] from section listings instead.
    """
    index = {}
    response = session.get(
        f"{base_url}/library/sections",
        params={"X-Plex-Token": token},
        headers=REQUEST_HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    for section in response.json()["MediaContainer"].get("Directory", []):
        if section.get("type") != "movie":
            continue
        response = session.get(
            f"{base_url}/library/sections/{section['key']}/all",
            params={"includeGuids": "1", "X-Plex-Token": token},
            headers=REQUEST_HEADERS,
            timeout=120,
        )
        response.raise_for_status()
        for item in response.json()["MediaContainer"].get("Metadata", []):
            for guid in item.get("Guid") or []:
                gid = guid.get("id") or ""
                if gid.startswith("tmdb://"):
                    tmdb_id = gid.split("://", 1)[1]
                    if tmdb_id and tmdb_id not in index:
                        index[tmdb_id] = item["ratingKey"]
                    break
    return index


def resolve_rating_key(session, base_url, token, title, year, tmdb_id, tmdb_index=None):
    if tmdb_index and tmdb_id in tmdb_index:
        return get_metadata(session, base_url, token, tmdb_index[tmdb_id])

    seen_keys = set()
    for query in title_search_queries(title):
        response = session.get(
            f"{base_url}/search",
            params={"query": query, "X-Plex-Token": token},
            headers=REQUEST_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        for item in response.json()["MediaContainer"].get("Metadata", []):
            if item.get("type") != "movie":
                continue
            rating_key = item["ratingKey"]
            if rating_key in seen_keys:
                continue
            seen_keys.add(rating_key)
            metadata = get_metadata(session, base_url, token, rating_key)
            for guid in metadata.get("Guid", []):
                if guid.get("id") == f"tmdb://{tmdb_id}":
                    return metadata
    return None


def rate_item(session, base_url, token, rating_key, plex_rating):
    response = session.get(
        f"{base_url}/:/rate",
        params={
            "identifier": "com.plexapp.plugins.library",
            "key": rating_key,
            "rating": str(plex_rating),
            "X-Plex-Token": token,
        },
        timeout=30,
    )
    response.raise_for_status()


def sync_once():
    base_url, token = load_plex_config()
    rss_items = fetch_rss_items()
    session = requests.Session()
    tmdb_index = build_tmdb_index(session, base_url, token)
    updated = 0
    unchanged = 0
    missing = []

    for tmdb_id, data in rss_items.items():
        metadata = resolve_rating_key(
            session, base_url, token, data["title"], data["year"], tmdb_id, tmdb_index
        )
        if not metadata:
            missing.append(f"{data['title']} ({tmdb_id})")
            continue
        current = metadata.get("userRating")
        desired = float(data["plex_rating"])
        if current == desired:
            unchanged += 1
            continue
        rate_item(session, base_url, token, metadata["ratingKey"], data["plex_rating"])
        updated += 1

    print(
        f"RSS items: {len(rss_items)} | updated: {updated} | unchanged: {unchanged} | missing: {len(missing)}",
        flush=True,
    )
    if missing:
        print("Missing:", ", ".join(missing[:10]), flush=True)


def main():
    while True:
        try:
            sync_once()
        except Exception as exc:  # transient Letterboxd/Plex/DNS errors: log and retry next cycle
            msg = re.sub(r"(X-Plex-Token=)[^&\s'\"]+", r"\1<redacted>", str(exc))
            print(f"Sync failed, will retry next cycle: {type(exc).__name__}: {msg}", flush=True)
        time.sleep(SYNC_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
