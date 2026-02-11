def human_size(size_bytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def get_image_url(images, cover_type="poster"):
    """Extract image URL by cover type from an images array (Radarr/Sonarr payloads).

    Args:
        images: list of {coverType, remoteUrl, url} dicts
        cover_type: "poster", "fanart", "banner", etc.
    """
    if not images:
        return None
    for img in images:
        if img.get("coverType") == cover_type:
            url = img.get("remoteUrl") or img.get("url")
            if url:
                # Use w342 for poster, w780 for fanart on TMDB
                # Valid TMDB sizes: w92, w154, w185, w342, w500, w780, original
                if "image.tmdb.org/t/p/original" in url:
                    size = "w342" if cover_type == "poster" else "w780"
                    url = url.replace("/t/p/original/", f"/t/p/{size}/")
                return url
    return None


def format_runtime(minutes):
    """Convert minutes to 'Xh Ym' format."""
    if not minutes:
        return ""
    h, m = divmod(int(minutes), 60)
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def movie_links(tmdb_id, imdb_id):
    """Build TMDb/IMDb/Trakt link string for a movie."""
    parts = []
    if tmdb_id:
        parts.append(f"[TMDb](https://www.themoviedb.org/movie/{tmdb_id})")
    if imdb_id:
        parts.append(f"[IMDb](https://www.imdb.com/title/{imdb_id})")
    if tmdb_id:
        parts.append(f"[Trakt](https://trakt.tv/search/tmdb/{tmdb_id}?id_type=movie)")
    if tmdb_id:
        parts.append(f"[Letterboxd](https://letterboxd.com/tmdb/{tmdb_id})")
    return " • ".join(parts)


def series_links(tvdb_id, imdb_id, tmdb_id=None):
    """Build TVDb/IMDb/Trakt link string for a series."""
    parts = []
    if tmdb_id:
        parts.append(f"[TMDb](https://www.themoviedb.org/tv/{tmdb_id})")
    if tvdb_id:
        parts.append(f"[TVDb](https://thetvdb.com/?id={tvdb_id}&tab=series)")
    if imdb_id:
        parts.append(f"[IMDb](https://www.imdb.com/title/{imdb_id})")
    if tvdb_id:
        parts.append(f"[Trakt](https://trakt.tv/search/tvdb/{tvdb_id}?id_type=show)")
    return " • ".join(parts)


def format_languages(languages):
    """Format a languages array into a string: Portuguese, English."""
    if not languages:
        return ""
    names = [l.get("name", "") for l in languages if l.get("name")]
    return ", ".join(names)


def format_ratings(ratings):
    """Format ratings dict into 'TMDb: 7.68 • IMDb: 8.0/10'."""
    if not ratings:
        return ""
    parts = []
    tmdb = ratings.get("tmdb", {}).get("value")
    imdb = ratings.get("imdb", {}).get("value")
    if tmdb:
        parts.append(f"TMDb: {tmdb}")
    if imdb:
        parts.append(f"IMDb: {imdb}/10")
    return " • ".join(parts)


def clean_template(template):
    """Clean a multiline f-string template into a proper markdown message.

    Usage in formatters — write your layout as a readable markdown block:

        message = clean_template(f'''
        **{title}**
        {episodes}

        > Grabbed from **{indexer}**

        {quality_line}
        {size_line}

        {cf_line}

        {poster_line}
        ''')

    How it works:
      - Strips leading indentation (so templates can be indented in code)
      - Lines that are empty or whitespace-only become paragraph breaks
      - Consecutive blank lines are collapsed into one paragraph break
      - Leading/trailing blank lines are removed
    """
    lines = template.strip().splitlines()

    # Strip indentation from each line
    stripped = [line.strip() for line in lines]

    # Collapse: consecutive empty lines -> single empty line
    result = []
    for line in stripped:
        if line == "" and result and result[-1] == "":
            continue
        result.append(line)

    # Trim leading/trailing empty lines
    while result and result[0] == "":
        result.pop(0)
    while result and result[-1] == "":
        result.pop()

    return "\n\n".join("\n".join(g) for g in _group_lines(result))


def _group_lines(lines):
    """Split lines into groups separated by empty strings.

    Lines within a group join with \\n (e.g. list items stay together).
    Groups join with \\n\\n (paragraph breaks).
    """
    groups = []
    current = []
    for line in lines:
        if line == "":
            if current:
                groups.append(current)
                current = []
        else:
            current.append(line)
    if current:
        groups.append(current)
    return groups
