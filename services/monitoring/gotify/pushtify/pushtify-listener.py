import os
import json
import re
import websocket
import requests

# Required config
pushover_userkey = os.environ["PUSHOVER_USERKEY"]
gotify_host = os.environ["GOTIFY_HOST"]
gotify_client_token = os.environ["GOTIFY_TOKEN"]
gotify_protocol = os.environ.get("GOTIFY_PROTOCOL", "https")
gotify_api_user = os.environ.get("GOTIFY_API_USER", "")
gotify_api_pass = os.environ.get("GOTIFY_API_PASS", "")
pushover_default_token = os.environ.get("PUSHOVER_DEFAULT_TOKEN", "")

# Protocol mapping
ws_protocol = "ws" if gotify_protocol == "http" else "wss"
http_url = f"{gotify_protocol}://{gotify_host}"

PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"

# app_id -> {name, pushover_token}
app_map = {}


def env_var_name(gotify_app_name):
    """Derive env var name from Gotify app name: sonarr -> SONARR_PUSHOVER_TOKEN"""
    return gotify_app_name.upper().replace("-", "_") + "_PUSHOVER_TOKEN"


def fetch_gotify_apps():
    """Fetch all Gotify applications and build the app mapping."""
    if not gotify_api_user:
        print("GOTIFY_API_USER not set, skipping app fetch")
        return

    try:
        resp = requests.get(
            f"{http_url}/application",
            auth=(gotify_api_user, gotify_api_pass),
            timeout=10,
        )
        resp.raise_for_status()
        apps = resp.json()
    except Exception as e:
        print(f"Failed to fetch Gotify applications: {e}")
        return

    fresh_map = {}
    for app in apps:
        app_id = app["id"]
        name = app["name"]

        var_name = env_var_name(name)
        token = os.environ.get(var_name, "")

        fresh_map[app_id] = {
            "name": name,
            "pushover_token": token,
        }

        status = "mapped" if token else "unmapped (no env var)"
        print(f"  {name} (id={app_id}): {status}")

    app_map.clear()
    app_map.update(fresh_map)


def map_priority(priority):
    """Map Gotify priority to Pushover priority."""
    if priority <= 0:
        return "-1"
    if priority <= 3:
        return "0"
    if priority <= 7:
        return "1"
    return "2"


def markdown_to_pushover(text):
    """Convert markdown to Pushover-compatible HTML.

    Pushover supports: <b>, <i>, <u>, <a href="">, <font color="">
    """
    # Remove images (Pushover doesn't render them inline)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # Convert markdown links [text](url) -> <a href="url">text</a>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    # Bold **text** -> <b>text</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # Italic *text* -> <i>text</i>
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)

    # Code blocks ```...``` -> collapse to single line
    def _code_to_inline(m):
        lines = [l.strip() for l in m.group(1).strip().splitlines() if l.strip()]
        return " | ".join(lines)
    text = re.sub(r"```\w*\n?(.*?)```", _code_to_inline, text, flags=re.DOTALL)

    # Inline code `text` -> just strip backticks
    text = re.sub(r"`(.+?)`", r"\1", text)

    # Blockquote > text -> strip the >
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)

    # List items - text -> bullet
    text = re.sub(r"^-\s+", "• ", text, flags=re.MULTILINE)

    # Clean up extra blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def download_image(url):
    """Download an image from a URL for Pushover attachment. Returns (filename, bytes) or None."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200 and len(resp.content) < 2_500_000:  # Pushover 2.5MB limit
            ext = url.rsplit(".", 1)[-1].split("?")[0] if "." in url else "jpg"
            return (f"poster.{ext}", resp.content, "image/jpeg")
        print(f"Image skipped: status={resp.status_code} size={len(resp.content)}")
    except Exception as e:
        print(f"Failed to download image {url}: {e}")
    return None


def send_pushover(token, title, message, priority, image_url=None):
    """Send notification to Pushover API."""
    html_message = markdown_to_pushover(message)
    data = {
        "token": token,
        "user": pushover_userkey,
        "title": title,
        "message": html_message,
        "priority": priority,
        "html": "1",
    }
    if priority == "2":
        data["retry"] = "60"
        data["expire"] = "3600"

    # Attach poster image if available
    files = None
    img = download_image(image_url)
    if img:
        files = {"attachment": img}

    try:
        resp = requests.post(PUSHOVER_API_URL, data=data, files=files, timeout=15)
        if resp.status_code == 200:
            return True
        print(f"Pushover API error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Failed to send Pushover notification: {e}")
    return False


def format_shoutrrr(body):
    """Reformat Shoutrrr notification body into a cleaner title + message.

    Input:  "[CPU] High CPU Usage - Agent: **ds423plus** | CPU: **99.7%** (threshold: 29%)"
    Output: ("CPU Alert", "High CPU Usage\nAgent: ds423plus\nCPU: 99.7% (threshold: 29%)")
    """
    m = re.match(r"\[(\w+)\]\s*(.+)", body)
    if not m:
        return None, body
    tag = m.group(1).upper()
    rest = m.group(2)

    # Strip markdown bold for clean parsing, we'll re-add formatting later
    rest = re.sub(r"\*\*(.+?)\*\*", r"\1", rest)

    # Split "Description - Key: val | Key: val" into lines
    parts = re.split(r"\s*[|\-]\s*", rest, maxsplit=1)
    description = parts[0].strip()
    details = parts[1].strip() if len(parts) > 1 else ""

    # Convert remaining "Key: val | Key: val" into separate lines
    lines = []
    if details:
        for part in details.split("|"):
            lines.append(part.strip())

    return description, "\n".join(lines)


def on_message(ws, message):
    try:
        msg = json.loads(message)
        app_id = msg.get("appid")
        title = msg.get("title", "Gotify")
        body = msg.get("message", "")
        priority = map_priority(msg.get("priority", 0))

        # Reformat generic Shoutrrr notifications
        if title == "Shoutrrr notification":
            shoutrrr_title, body = format_shoutrrr(body)
            title = shoutrrr_title or "Alert"

        if app_id not in app_map and gotify_api_user:
            print(f"Unknown app id={app_id}, refreshing Gotify app mapping...")
            fetch_gotify_apps()

        app_info = app_map.get(app_id, {})
        app_name = app_info.get("name", f"unknown-{app_id}")
        token = app_info.get("pushover_token", "") or pushover_default_token

        if not token:
            print(f"No Pushover token for Gotify app '{app_name}' (id={app_id}), skipping")
            return

        # Extract image URL from Gotify extras (set by gotify-middleware)
        extras = msg.get("extras", {})
        image_url = extras.get("client::notification", {}).get("bigImageUrl")

        source = "per-app" if app_info.get("pushover_token") else "default"
        if send_pushover(token, title, body, priority, image_url):
            print(f"Forwarded [{app_name}] ({source}): {title}")
        else:
            print(f"Failed to forward [{app_name}]: {title}")
    except Exception as e:
        print(f"Error handling message: {e}")


def on_error(ws, error):
    print(f"WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg):
    print(f"Connection closed: {close_status_code} {close_msg}")


def on_open(ws):
    print("Connected to Gotify WebSocket stream")


if __name__ == "__main__":
    print("Pushtify - Gotify to Pushover bridge")
    print("=" * 40)

    print("\nFetching Gotify applications...")
    fetch_gotify_apps()

    mapped = sum(1 for a in app_map.values() if a["pushover_token"])
    total = len(app_map)
    print(f"\nApps: {mapped}/{total} mapped to Pushover tokens")
    if pushover_default_token:
        print(f"Default Pushover token: set (unmapped apps will use it)")
    else:
        print(f"Default Pushover token: not set (unmapped apps will be skipped)")

    print(f"\nConnecting to {ws_protocol}://{gotify_host}/stream ...")
    ws_url = f"{ws_protocol}://{gotify_host}/stream"
    wsapp = websocket.WebSocketApp(
        ws_url,
        header=[f"X-Gotify-Key: {gotify_client_token}"],
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    wsapp.run_forever(reconnect=5)
