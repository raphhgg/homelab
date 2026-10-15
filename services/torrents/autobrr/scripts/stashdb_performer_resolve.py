#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


GRAPHQL_QUERY = """
query($term:String!){
  searchPerformer(term:$term, limit:5) {
    id
    name
    gender
    disambiguation
    aliases
    urls { url }
  }
}
""".strip()


@dataclass
class SearchResult:
    id: str
    name: str
    gender: str | None
    disambiguation: str | None
    aliases: list[str]
    urls: list[str]


def normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def score_result(term: str, result: SearchResult) -> tuple[int, list[str]]:
    notes: list[str] = []
    score = 0

    term_norm = normalize(term)
    name_norm = normalize(result.name)
    alias_norms = {normalize(alias): alias for alias in result.aliases}

    if result.gender == "FEMALE":
        score += 30
        notes.append("female")
    elif result.gender:
        score -= 20
        notes.append(f"gender:{result.gender.lower()}")

    if name_norm == term_norm:
        score += 100
        notes.append("exact-name")
    elif term_norm in alias_norms:
        score += 90
        notes.append(f"exact-alias:{alias_norms[term_norm]}")
    elif name_norm.startswith(term_norm) or term_norm.startswith(name_norm):
        score += 40
        notes.append("prefix-match")
    elif any(term_norm in alias or alias in term_norm for alias in alias_norms):
        score += 25
        notes.append("alias-partial")

    if result.disambiguation:
        notes.append("has-disambiguation")

    return score, notes


def graphql_post(endpoint: str, api_key: str, payload: dict[str, object]) -> dict[str, object]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "ApiKey": api_key,
        },
        method="POST",
    )

    context = ssl.create_default_context()
    with urllib.request.urlopen(request, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_candidates(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data, list):
        values = [item for item in data if isinstance(item, str)]
    else:
        performers = data.get("performers", [])
        values = []
        for performer in performers:
            if isinstance(performer, dict):
                name = performer.get("performer")
                if isinstance(name, str):
                    values.append(name)
            elif isinstance(performer, str):
                values.append(performer)

    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = normalize(value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def search_performer(endpoint: str, api_key: str, term: str) -> list[SearchResult]:
    payload = {
        "query": GRAPHQL_QUERY,
        "variables": {"term": term},
    }
    response = graphql_post(endpoint, api_key, payload)

    if "errors" in response:
        raise RuntimeError(json.dumps(response["errors"]))

    raw_results = response.get("data", {}).get("searchPerformer", [])
    parsed: list[SearchResult] = []
    for item in raw_results:
        parsed.append(
            SearchResult(
                id=item["id"],
                name=item["name"],
                gender=item.get("gender"),
                disambiguation=item.get("disambiguation"),
                aliases=item.get("aliases") or [],
                urls=[url["url"] for url in item.get("urls") or [] if "url" in url],
            )
        )
    return parsed


def build_resolution(endpoint: str, api_key: str, term: str) -> dict[str, object]:
    results = search_performer(endpoint, api_key, term)
    ranked: list[dict[str, object]] = []

    for result in results:
        score, notes = score_result(term, result)
        ranked.append(
            {
                "id": result.id,
                "name": result.name,
                "gender": result.gender,
                "disambiguation": result.disambiguation,
                "aliases": result.aliases,
                "urls": result.urls,
                "score": score,
                "notes": notes,
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    best = ranked[0] if ranked else None

    resolution = {
        "input_name": term,
        "status": "unmatched",
        "canonical_name": None,
        "match": None,
        "candidates": ranked,
    }

    if not best:
        return resolution

    second_score = ranked[1]["score"] if len(ranked) > 1 else None
    best_score = best["score"]

    if best_score >= 120 and (second_score is None or best_score - second_score >= 20):
        resolution["status"] = "matched"
        resolution["canonical_name"] = best["name"]
        resolution["match"] = best
    elif best_score >= 60:
        resolution["status"] = "ambiguous"
        resolution["canonical_name"] = best["name"]
        resolution["match"] = best

    return resolution


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve parsed performer names against StashDB canonical metadata."
    )
    parser.add_argument("input", type=Path, help="JSON file from bitporn_bookmarks_extract.py --json")
    parser.add_argument("--endpoint", default="https://stashdb.org/graphql")
    parser.add_argument("--api-key", required=True)
    args = parser.parse_args()

    candidates = parse_candidates(args.input)
    resolutions: list[dict[str, object]] = []

    for performer in candidates:
        try:
            resolutions.append(build_resolution(args.endpoint, args.api_key, performer))
        except (urllib.error.URLError, RuntimeError) as exc:
            resolutions.append(
                {
                    "input_name": performer,
                    "status": "error",
                    "canonical_name": None,
                    "match": None,
                    "candidates": [],
                    "error": str(exc),
                }
            )

    json.dump(
        {
            "endpoint": args.endpoint,
            "performer_count": len(candidates),
            "resolutions": resolutions,
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
