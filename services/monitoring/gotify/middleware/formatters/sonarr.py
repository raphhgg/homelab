from formatters.utils import (
    human_size, get_image_url, format_runtime, format_languages,
    format_ratings, series_links, clean_template,
)


def format_webhook(payload):
    event_type = payload.get("eventType", "")

    if event_type == "Grab":
        return _format_grab(payload)
    elif event_type in ("Download", "ImportComplete"):
        return _format_import(payload)
    elif event_type == "Health":
        return _format_health(payload)
    elif event_type == "HealthRestored":
        return _format_health_restored(payload)
    elif event_type == "Test":
        return "Test", "Sonarr webhook test successful.", 3, None
    else:
        return event_type or "Sonarr", payload.get("message", str(payload)), 5, None


def _episode_str(episodes):
    """Format episodes: S05E16 - Felina (one per line)."""
    lines = []
    for ep in episodes:
        s = ep.get("seasonNumber", 0)
        e = ep.get("episodeNumber", 0)
        ep_title = ep.get("title", "")
        lines.append(f"S{s:02d}E{e:02d} - {ep_title}")
    return "\n".join(lines)


def _episode_overview(episodes):
    """Get the first episode overview (for single episode grabs)."""
    if len(episodes) == 1:
        overview = episodes[0].get("overview", "")
        if len(overview) > 300:
            overview = overview[:300] + "..."
        return overview
    return ""


def _format_grab(p):
    series = p.get("series", {})
    episodes = p.get("episodes", [])
    release = p.get("release", {})

    # --- Extract all data ---
    title = series.get("title", "Unknown")
    year = series.get("year", "")
    header = f"{title} ({year})" if year else title
    episodes_block = _episode_str(episodes)

    quality = release.get("quality", "")
    group = release.get("releaseGroup", "")
    indexer = release.get("indexer", "")
    size = release.get("size", 0)
    size_str = human_size(size) if size else ""
    client = p.get("downloadClient", "")

    # Episode overview for single-episode grabs
    overview = _episode_overview(episodes)

    tvdb_id = series.get("tvdbId")
    imdb_id = series.get("imdbId")
    tmdb_id = series.get("tmdbId")
    ratings_str = format_ratings(series.get("ratings", {}))
    links_str = series_links(tvdb_id, imdb_id, tmdb_id)

    genres = series.get("genres", [])
    genres_str = ", ".join(genres) if genres else ""
    network = series.get("network", "")

    release_title = release.get("releaseTitle", "")
    lang_str = format_languages(release.get("languages", []))

    cfs = release.get("customFormats", [])
    cf_score = release.get("customFormatScore", 0)
    cf_names = ", ".join(cfs) if cfs and isinstance(cfs[0], str) else \
               ", ".join(cf.get("name", str(cf)) for cf in cfs) if cfs else ""

    poster = get_image_url(series.get("images", []), "poster")
    fanart = get_image_url(series.get("images", []), "fanart")

    # --- Conditional sections ---
    overview_line = f"*{overview}*" if overview else ""

    info_items = [x for x in [
        f"- `{quality}`" if quality else "",
        f"- **{size_str}**" if size_str else "",
        f"- **Indexer**: {indexer}" if indexer else "",
        f"- **Group**: {group}" if group else "",
        f"- **Client**: {client}" if client else "",
        f"- **Network**: {network}" if network else "",
    ] if x]
    info_section = "**Info**\n" + "\n".join(info_items) if info_items else ""

    ratings_section = f"**Ratings**\n- {ratings_str}" if ratings_str else ""
    links_line = links_str
    genres_section = f"**Genres**\n- {genres_str}" if genres_str else ""

    release_section = f"**Release**\n```\n{release_title}\n```" if release_title else ""

    lang_section = ""
    if lang_str:
        lang_section = f"**Languages**\n```\n{lang_str}\n```"

    cf_section = ""
    if cfs:
        cf_section = f"**Custom Formats**\n```\nScore: {cf_score}\nFormat: {cf_names}\n```"

    image_line = f"![fanart]({fanart})" if fanart else \
                 f"![poster]({poster})" if poster else ""

    # ── Message template ─────────────────────────────
    message = clean_template(f"""
        **{header}**
        {episodes_block}

        {overview_line}

        {info_section}

        {ratings_section}

        {links_line}

        {genres_section}

        {release_section}

        {lang_section}

        {cf_section}

        {image_line}
    """)

    return "Grabbed", message, 5, poster


def _format_import(p):
    series = p.get("series", {})
    episodes = p.get("episodes", [])
    ep_file = p.get("episodeFile", {})
    is_upgrade = p.get("isUpgrade", False)
    client = p.get("downloadClient", "")

    title = series.get("title", "Unknown")
    year = series.get("year", "")
    header = f"{title} ({year})" if year else title
    episodes_block = _episode_str(episodes)

    quality = ep_file.get("quality", "")
    group = ep_file.get("releaseGroup", "")
    upgrade_str = "Yes" if is_upgrade else "No"

    tvdb_id = series.get("tvdbId")
    imdb_id = series.get("imdbId")
    tmdb_id = series.get("tmdbId")
    links_str = series_links(tvdb_id, imdb_id, tmdb_id)

    poster = get_image_url(series.get("images", []), "poster")
    fanart = get_image_url(series.get("images", []), "fanart")

    quality_line = f"- Quality: `{quality}` | Group: **{group}**" if quality and group else \
                   f"- Quality: `{quality}`" if quality else \
                   f"- Group: **{group}**" if group else ""
    client_line = f"- Client: {client}" if client else ""
    links_line = links_str
    image_line = f"![fanart]({fanart})" if fanart else \
                 f"![poster]({poster})" if poster else ""

    message = clean_template(f"""
        **{header}**
        {episodes_block}

        > Imported (Upgrade: **{upgrade_str}**)

        {quality_line}
        {client_line}

        {links_line}

        {image_line}
    """)

    return "Imported", message, 5, poster


def _format_health(p):
    level = p.get("level", "Warning")
    msg = p.get("message", "")
    wiki_url = p.get("wikiUrl", "")

    wiki_line = f"[Wiki]({wiki_url})" if wiki_url else ""

    message = clean_template(f"""
        **{level}**

        {msg}

        {wiki_line}
    """)

    return "Health Issue", message, 8, None


def _format_health_restored(p):
    msg = p.get("message", "Health issue resolved")

    message = clean_template(f"""
        **Resolved**

        {msg}
    """)

    return "Health Restored", message, 3, None
