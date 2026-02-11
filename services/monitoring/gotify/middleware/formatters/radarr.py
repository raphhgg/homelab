from formatters.utils import (
    human_size, get_image_url, format_runtime, format_languages,
    format_ratings, movie_links, clean_template,
)


def format_webhook(payload):
    event_type = payload.get("eventType", "")

    if event_type == "Grab":
        return _format_grab(payload)
    elif event_type in ("Download", "ImportComplete"):
        return _format_import(payload)
    elif event_type == "MovieAdded":
        return _format_added(payload)
    elif event_type == "Health":
        return _format_health(payload)
    elif event_type == "HealthRestored":
        return _format_health_restored(payload)
    elif event_type == "Test":
        return "Test", "Radarr webhook test successful.", 3, None
    else:
        return event_type or "Radarr", payload.get("message", str(payload)), 5, None


def _format_grab(p):
    movie = p.get("movie", {})
    release = p.get("release", {})
    remote = p.get("remoteMovie", {})

    # --- Extract all data ---
    title = movie.get("title", "Unknown")
    year = movie.get("year", "")
    header = f"{title} ({year})" if year else title

    quality = release.get("quality", "")
    group = release.get("releaseGroup", "")
    indexer = release.get("indexer", "")
    size = release.get("size", 0)
    size_str = human_size(size) if size else ""
    client = p.get("downloadClient", "")
    runtime_str = format_runtime(movie.get("runtime", 0))
    release_date = movie.get("releaseDate", "")

    overview = movie.get("overview", "")
    if len(overview) > 300:
        overview = overview[:300] + "..."

    tmdb_id = movie.get("tmdbId") or remote.get("tmdbId")
    imdb_id = movie.get("imdbId") or remote.get("imdbId")
    ratings_str = format_ratings(movie.get("ratings", {}))
    links_str = movie_links(tmdb_id, imdb_id)

    genres = movie.get("genres", [])
    genres_str = ", ".join(genres) if genres else ""

    release_title = release.get("releaseTitle", "")
    lang_str = format_languages(release.get("languages", []))
    orig_lang = movie.get("originalLanguage", {}).get("name", "")

    cfs = release.get("customFormats", [])
    cf_score = release.get("customFormatScore", 0)
    cf_names = ", ".join(cfs) if cfs and isinstance(cfs[0], str) else \
               ", ".join(cf.get("name", str(cf)) for cf in cfs) if cfs else ""

    poster = get_image_url(movie.get("images", []), "poster")
    fanart = get_image_url(movie.get("images", []), "fanart")

    # --- Conditional sections (empty string = hidden by clean_template) ---
    overview_line = f"*{overview}*" if overview else ""

    info_items = [x for x in [
        f"- `{quality}`" if quality else "",
        f"- {runtime_str}" if runtime_str else "",
        f"- **{size_str}**" if size_str else "",
        f"- **Indexer**: {indexer}" if indexer else "",
        f"- **Group**: {group}" if group else "",
        f"- **Client**: {client}" if client else "",
        f"- **Released**: {release_date}" if release_date else "",
    ] if x]
    info_section = "**Info**\n" + "\n".join(info_items) if info_items else ""

    ratings_section = f"**Ratings**\n- {ratings_str}" if ratings_str else ""
    links_line = links_str
    genres_section = f"**Genres**\n- {genres_str}" if genres_str else ""

    release_section = f"**Release**\n```\n{release_title}\n```" if release_title else ""

    lang_section = ""
    if orig_lang or lang_str:
        lang_parts = []
        if orig_lang:
            lang_parts.append(f"Original: {orig_lang}")
        if lang_str:
            lang_parts.append(f"Release: {lang_str}")
        lang_section = "**Languages**\n```\n" + "\n".join(lang_parts) + "\n```"

    cf_section = ""
    if cfs:
        cf_section = f"**Custom Formats**\n```\nScore: {cf_score}\nFormat: {cf_names}\n```"

    image_line = f"![fanart]({fanart})" if fanart else \
                 f"![poster]({poster})" if poster else ""

    # ── Message template ─────────────────────────────
    # Edit this markdown block to change the notification layout.
    # Empty variables are automatically stripped.
    message = clean_template(f"""
        **{header}**

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
    movie = p.get("movie", {})
    movie_file = p.get("movieFile", {})
    remote = p.get("remoteMovie", {})
    is_upgrade = p.get("isUpgrade", False)
    client = p.get("downloadClient", "")

    title = movie.get("title", "Unknown")
    year = movie.get("year", "")
    header = f"{title} ({year})" if year else title

    quality = movie_file.get("quality", "")
    group = movie_file.get("releaseGroup", "")
    upgrade_str = "Yes" if is_upgrade else "No"

    tmdb_id = movie.get("tmdbId") or remote.get("tmdbId")
    imdb_id = movie.get("imdbId") or remote.get("imdbId")
    links_str = movie_links(tmdb_id, imdb_id)

    poster = get_image_url(movie.get("images", []), "poster")
    fanart = get_image_url(movie.get("images", []), "fanart")

    quality_line = f"- Quality: `{quality}` | Group: **{group}**" if quality and group else \
                   f"- Quality: `{quality}`" if quality else \
                   f"- Group: **{group}**" if group else ""
    client_line = f"- Client: {client}" if client else ""
    links_line = links_str
    image_line = f"![fanart]({fanart})" if fanart else \
                 f"![poster]({poster})" if poster else ""

    message = clean_template(f"""
        **{header}**

        > Imported (Upgrade: **{upgrade_str}**)

        {quality_line}
        {client_line}

        {links_line}

        {image_line}
    """)

    return "Imported", message, 5, poster


def _format_added(p):
    movie = p.get("movie", {})
    remote = p.get("remoteMovie", {})

    title = movie.get("title", "Unknown")
    year = movie.get("year", "")
    header = f"{title} ({year})" if year else title

    overview = movie.get("overview", "")
    if len(overview) > 300:
        overview = overview[:300] + "..."

    tmdb_id = movie.get("tmdbId") or remote.get("tmdbId")
    imdb_id = movie.get("imdbId") or remote.get("imdbId")
    links_str = movie_links(tmdb_id, imdb_id)
    genres = movie.get("genres", [])
    genres_str = ", ".join(genres) if genres else ""

    poster = get_image_url(movie.get("images", []), "poster")

    overview_line = f"*{overview}*" if overview else ""
    genres_line = f"**Genres**: {genres_str}" if genres_str else ""
    links_line = links_str
    poster_line = f"![poster]({poster})" if poster else ""

    message = clean_template(f"""
        **{header}**

        > Added to library

        {overview_line}

        {genres_line}

        {links_line}

        {poster_line}
    """)

    return "Movie Added", message, 3, poster


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
