from formatters.utils import human_size, clean_template


def format_webhook(payload):
    event = payload.get("event", "")

    if event == "action.approved":
        return _format_approved(payload)
    elif event == "action.rejected":
        return _format_rejected(payload)
    elif event == "action.error":
        return _format_error(payload)
    elif event == "test":
        return "Test", "Autobrr webhook test successful.", 3, None
    elif event in ("irc.disconnected", "irc.reconnected"):
        return _format_irc(payload)
    elif event == "app.update_available":
        return "Update Available", "A new Autobrr version is available.", 3, None
    else:
        return event or "Autobrr", str(payload.get("data", "")), 5, None


def _format_approved(p):
    data = p.get("data", {})
    release = data.get("release", {})
    indexer = data.get("indexer", {})
    filt = data.get("filter", {})
    action = data.get("action", {})

    name = release.get("name", "Unknown")
    title = release.get("title", "")
    year = release.get("year", 0)
    header = f"{title} ({year})" if title and year else name
    resolution = release.get("resolution", "")
    source = release.get("source", "")
    quality_str = " ".join(filter(None, [resolution, source]))
    group = release.get("group", "")
    size = release.get("size", 0)
    size_str = human_size(size) if size else ""
    freeleech = release.get("freeleech", False)
    indexer_name = indexer.get("name", "")
    filter_name = filt.get("name", "")
    target = action.get("name", "") or action.get("type", "")

    # --- Conditional lines ---
    action_line = f"> Approved → **{target}**" if target else "> Approved"
    indexer_line = f"- Indexer: **{indexer_name}** | Filter: {filter_name}" if indexer_name and filter_name else \
                   f"- Indexer: **{indexer_name}**" if indexer_name else \
                   f"- Filter: {filter_name}" if filter_name else ""
    quality_line = f"- Quality: `{quality_str}` | Group: **{group}**" if quality_str and group else \
                   f"- Quality: `{quality_str}`" if quality_str else \
                   f"- Group: **{group}**" if group else ""
    size_line = f"- Size: **{size_str}** | Freeleech: Yes" if size_str and freeleech else \
                f"- Size: **{size_str}**" if size_str else \
                f"- Freeleech: Yes" if freeleech else ""

    # ── Message template ─────────────────────────────
    message = clean_template(f"""
        **{header}**

        {action_line}

        {indexer_line}
        {quality_line}
        {size_line}
    """)

    return "Push Approved", message, 5, None


def _format_rejected(p):
    data = p.get("data", {})
    release = data.get("release", {})
    indexer = data.get("indexer", {})
    filt = data.get("filter", {})
    result = data.get("result", {})

    name = release.get("name", "Unknown")
    rejections = result.get("rejections", [])
    indexer_name = indexer.get("name", "")
    filter_name = filt.get("name", "")

    indexer_line = f"- Indexer: **{indexer_name}** | Filter: {filter_name}" if indexer_name and filter_name else \
                   f"- Indexer: **{indexer_name}**" if indexer_name else \
                   f"- Filter: {filter_name}" if filter_name else ""
    rejections_line = f"- Rejections: {', '.join(rejections)}" if rejections else ""

    message = clean_template(f"""
        **{name}**

        > Rejected

        {indexer_line}
        {rejections_line}
    """)

    return "Push Rejected", message, 5, None


def _format_error(p):
    data = p.get("data", {})
    release = data.get("release", {})
    result = data.get("result", {})

    name = release.get("name", "Unknown")
    status_msg = result.get("status_message", "Unknown error")

    message = clean_template(f"""
        **{name}**

        > Error: {status_msg}
    """)

    return "Push Error", message, 8, None


def _format_irc(p):
    event = p.get("event", "")
    if event == "irc.disconnected":
        return "IRC Disconnected", "An IRC connection was lost.", 8, None
    return "IRC Reconnected", "IRC connection restored.", 3, None
