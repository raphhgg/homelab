from datetime import datetime, timezone, timedelta

from formatters.utils import clean_template

# Brussels timezone (CET/CEST)
TZ_BRUSSELS = timezone(timedelta(hours=1))


def format_webhook(payload):
    """Format Uptime Kuma webhook into a Gotify notification.

    Payload keys vary: heartbeatJSON/heartbeat, monitorJSON/monitor.
    """
    heartbeat = payload.get("heartbeatJSON") or payload.get("heartbeat") or {}
    monitor = payload.get("monitorJSON") or payload.get("monitor") or {}

    status = heartbeat.get("status", 0)  # 0=down, 1=up
    monitor_name = monitor.get("name", "Unknown")

    if status == 1:
        return _format_up(monitor, heartbeat)
    else:
        return _format_down(monitor, heartbeat)


def _get_service_url(monitor):
    """Extract the service URL from monitor config."""
    url = monitor.get("url", "")
    if url:
        return url
    hostname = monitor.get("hostname", "")
    port = monitor.get("port")
    if hostname and port:
        return f"http://{hostname}:{port}/"
    if hostname:
        return hostname
    return ""


def _format_duration(seconds):
    """Format duration in seconds to human-readable string."""
    if not seconds or seconds <= 0:
        return "0s"
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs and not days:
        parts.append(f"{secs}s")
    return " ".join(parts) if parts else "0s"


def _format_time(time_str):
    """Format heartbeat time to readable string with timezone."""
    if not time_str:
        return ""
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        dt_local = dt.astimezone(TZ_BRUSSELS)
        return dt_local.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return time_str


def _format_went_offline(time_str):
    """Format the went-offline time to a readable date string."""
    if not time_str:
        return ""
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        dt_local = dt.astimezone(TZ_BRUSSELS)
        return dt_local.strftime("%A, %d %B %Y at %H:%M")
    except (ValueError, TypeError):
        return time_str


def _format_up(monitor, heartbeat):
    name = monitor.get("name", "Unknown")
    url = _get_service_url(monitor)
    ping = heartbeat.get("ping", "")
    duration = heartbeat.get("duration", 0)
    time_str = heartbeat.get("time", "")

    url_line = f"**URL**: {url}" if url else ""
    duration_line = f"**Downtime Duration**: {_format_duration(duration)}" if duration else ""
    ping_line = f"**Ping**: {ping} ms" if ping else ""
    time_line = f"**Time (Europe/Brussels)**: {_format_time(time_str)}" if time_str else ""

    message = clean_template(f"""
        {url_line}
        {duration_line}
        {time_line}
        {ping_line}
    """)

    title = f"✅ {name} is up!"
    return title, message, 3, None


def _format_down(monitor, heartbeat):
    name = monitor.get("name", "Unknown")
    url = _get_service_url(monitor)
    msg = heartbeat.get("msg", "")
    time_str = heartbeat.get("time", "")
    ping = heartbeat.get("ping", "")

    url_line = f"**URL**: {url}" if url else ""
    msg_line = f"**Error**: {msg}" if msg else ""
    time_line = f"**Went Offline**: {_format_went_offline(time_str)}" if time_str else ""
    ping_line = f"**Last Ping**: {ping} ms" if ping else ""

    message = clean_template(f"""
        {url_line}
        {msg_line}
        {time_line}
        {ping_line}
    """)

    title = f"🔴 {name} is down!"
    return title, message, 3, None
