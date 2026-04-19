import html
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing
from urllib.parse import urlparse

import requests
from flask import Flask, Response, jsonify, redirect, request


app = Flask(__name__)

DB_PATH = os.getenv("DB_PATH", "/data/invites.db")
BROKER_PUBLIC_URL = os.getenv("BROKER_PUBLIC_URL", "").rstrip("/")
BROKER_ADMIN_API_KEY = os.getenv("BROKER_ADMIN_API_KEY", "")
POCKET_ID_BASE_URL = os.getenv("POCKET_ID_BASE_URL", "").rstrip("/")
POCKET_ID_API_KEY = os.getenv("POCKET_ID_API_KEY", "")
POCKET_SIGNUP_TOKEN_TTL = os.getenv("POCKET_SIGNUP_TOKEN_TTL", "24h")
INVITE_TOKEN_TTL_HOURS = int(os.getenv("INVITE_TOKEN_TTL_HOURS", "168"))
WIZARR_BASE_URL = os.getenv("WIZARR_BASE_URL", "").rstrip("/")
WIZARR_PUBLIC_URL = os.getenv("WIZARR_PUBLIC_URL", WIZARR_BASE_URL).rstrip("/")
WIZARR_API_KEY = os.getenv("WIZARR_API_KEY", "")
INVITE_SERVER_NAME = os.getenv("INVITE_SERVER_NAME", "raphh's media server")
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def parse_group_ids() -> list[str]:
    value = os.getenv("POCKET_SIGNUP_USER_GROUP_IDS", "").strip()
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


POCKET_SIGNUP_USER_GROUP_IDS = parse_group_ids()


def parse_int_list_env(name: str) -> list[int]:
    value = os.getenv(name, "").strip()
    if not value:
        return []
    values: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(int(item))
        except ValueError:
            continue
    return values


WIZARR_DEFAULT_SERVER_IDS = parse_int_list_env("WIZARR_DEFAULT_SERVER_IDS")
WIZARR_DEFAULT_LIBRARY_IDS = parse_int_list_env("WIZARR_DEFAULT_LIBRARY_IDS")
WIZARR_DEFAULT_EXPIRES_IN_DAYS = os.getenv("WIZARR_DEFAULT_EXPIRES_IN_DAYS", "")
WIZARR_DEFAULT_DURATION = os.getenv("WIZARR_DEFAULT_DURATION", "unlimited")
WIZARR_DEFAULT_UNLIMITED = os.getenv("WIZARR_DEFAULT_UNLIMITED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
WIZARR_DEFAULT_ALLOW_DOWNLOADS = os.getenv(
    "WIZARR_DEFAULT_ALLOW_DOWNLOADS", "false"
).lower() in {"1", "true", "yes", "on"}
WIZARR_DEFAULT_ALLOW_LIVE_TV = os.getenv("WIZARR_DEFAULT_ALLOW_LIVE_TV", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
WIZARR_DEFAULT_ALLOW_MOBILE_UPLOADS = os.getenv(
    "WIZARR_DEFAULT_ALLOW_MOBILE_UPLOADS", "false"
).lower() in {"1", "true", "yes", "on"}


def db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(db_connection()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS invites (
                token TEXT PRIMARY KEY,
                wizarr_invite_url TEXT NOT NULL,
                email TEXT,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                activated_at INTEGER,
                activation_url TEXT,
                signup_token_id TEXT,
                pocket_id_completed_at INTEGER,
                last_error TEXT
            )
            """
        )
        for statement in (
            "ALTER TABLE invites ADD COLUMN signup_token_id TEXT",
            "ALTER TABLE invites ADD COLUMN pocket_id_completed_at INTEGER",
        ):
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                pass
        conn.commit()


def now_ts() -> int:
    return int(time.time())


def is_valid_url(value: str) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def require_admin_key() -> bool:
    provided = request.headers.get("X-ADMIN-API-KEY", "")
    return bool(BROKER_ADMIN_API_KEY) and secrets.compare_digest(provided, BROKER_ADMIN_API_KEY)


def get_invite(token: str) -> sqlite3.Row | None:
    with closing(db_connection()) as conn:
        row = conn.execute("SELECT * FROM invites WHERE token = ?", (token,)).fetchone()
    return row


def invite_url(token: str) -> str:
    if BROKER_PUBLIC_URL:
        return f"{BROKER_PUBLIC_URL}/i/{token}"
    return f"{request.url_root.rstrip('/')}/i/{token}"


def create_pocket_signup_link() -> tuple[str, str]:
    if not POCKET_ID_BASE_URL or not POCKET_ID_API_KEY:
        raise RuntimeError("Pocket ID API configuration is incomplete")

    invalid_group_ids = [
        group_id for group_id in POCKET_SIGNUP_USER_GROUP_IDS if not UUID_RE.match(group_id)
    ]
    if invalid_group_ids:
        raise RuntimeError(
            "POCKET_SIGNUP_USER_GROUP_IDS must contain Pocket ID group IDs (UUIDs), "
            f"not names: {', '.join(invalid_group_ids)}"
        )

    payload = {
        "ttl": POCKET_SIGNUP_TOKEN_TTL,
        "usageLimit": 1,
        "userGroupIds": POCKET_SIGNUP_USER_GROUP_IDS,
    }

    response = requests.post(
        f"{POCKET_ID_BASE_URL}/api/signup-tokens",
        headers={"X-API-KEY": POCKET_ID_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    response.raise_for_status()

    body = response.json()
    token = body.get("token")
    token_id = body.get("id")
    if not token or not token_id:
        raise RuntimeError("Pocket ID did not return a signup token")

    return f"{POCKET_ID_BASE_URL}/st/{token}", str(token_id)


def is_pocket_signup_completed(signup_token_id: str) -> bool:
    if not POCKET_ID_BASE_URL or not POCKET_ID_API_KEY:
        return False

    response = requests.get(
        f"{POCKET_ID_BASE_URL}/api/signup-tokens",
        headers={"X-API-KEY": POCKET_ID_API_KEY},
        params={"pagination[page]": 1, "pagination[limit]": 200},
        timeout=15,
    )
    response.raise_for_status()
    body = response.json()
    items = body.get("data", []) if isinstance(body, dict) else []

    for item in items:
        if str(item.get("id")) != signup_token_id:
            continue
        usage_count = item.get("usageCount", 0)
        usage_limit = item.get("usageLimit", 1)
        return int(usage_count) >= min(int(usage_limit), 1)

    return False


def refresh_invite_completion(token: str) -> sqlite3.Row | None:
    row = get_invite(token)
    if row is None:
        return None

    if row["pocket_id_completed_at"]:
        return row

    signup_token_id = row["signup_token_id"]
    if not signup_token_id:
        return row

    try:
        completed = is_pocket_signup_completed(signup_token_id)
    except Exception:
        return row

    if completed:
        with closing(db_connection()) as conn:
            conn.execute(
                """
                UPDATE invites
                SET pocket_id_completed_at = ?, status = 'ready', last_error = NULL
                WHERE token = ?
                """,
                (now_ts(), token),
            )
            conn.commit()
        return get_invite(token)

    return row


def create_wizarr_invite(data: dict) -> str:
    if not WIZARR_BASE_URL or not WIZARR_API_KEY:
        raise RuntimeError("Wizarr API configuration is incomplete")

    server_ids = data.get("server_ids")
    if server_ids is None:
        server_ids = WIZARR_DEFAULT_SERVER_IDS

    if not isinstance(server_ids, list) or not server_ids:
        raise RuntimeError("server_ids is required (request or WIZARR_DEFAULT_SERVER_IDS)")

    payload = {
        "server_ids": [int(x) for x in server_ids],
        "duration": data.get("duration", WIZARR_DEFAULT_DURATION),
        "unlimited": bool(data.get("unlimited", WIZARR_DEFAULT_UNLIMITED)),
        "allow_downloads": bool(
            data.get("allow_downloads", WIZARR_DEFAULT_ALLOW_DOWNLOADS)
        ),
        "allow_live_tv": bool(data.get("allow_live_tv", WIZARR_DEFAULT_ALLOW_LIVE_TV)),
        "allow_mobile_uploads": bool(
            data.get("allow_mobile_uploads", WIZARR_DEFAULT_ALLOW_MOBILE_UPLOADS)
        ),
    }

    library_ids = data.get("library_ids", WIZARR_DEFAULT_LIBRARY_IDS)
    if isinstance(library_ids, list) and library_ids:
        payload["library_ids"] = [int(x) for x in library_ids]

    expires_in_days = data.get("expires_in_days")
    if expires_in_days is None and WIZARR_DEFAULT_EXPIRES_IN_DAYS.strip():
        expires_in_days = WIZARR_DEFAULT_EXPIRES_IN_DAYS.strip()
    if expires_in_days not in (None, ""):
        payload["expires_in_days"] = int(expires_in_days)

    response = requests.post(
        f"{WIZARR_BASE_URL}/api/invitations",
        headers={"X-API-Key": WIZARR_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()

    body = response.json()
    invitation = body.get("invitation", {}) if isinstance(body, dict) else {}
    url = invitation.get("url")
    if not url:
        raise RuntimeError("Wizarr did not return an invitation URL")
    if url.startswith("/"):
        return f"{WIZARR_PUBLIC_URL}{url}"

    parsed_url = urlparse(url)
    parsed_base = urlparse(WIZARR_BASE_URL)
    if parsed_base.netloc and parsed_url.netloc == parsed_base.netloc:
        public_base = urlparse(WIZARR_PUBLIC_URL)
        return f"{public_base.scheme}://{public_base.netloc}{parsed_url.path}"
    return url


def create_broker_invite_record(
    wizarr_invite: str,
    email: str | None,
    expires_in_hours: int,
) -> dict:
    token = secrets.token_urlsafe(24)
    created_at = now_ts()
    expires_at = created_at + (expires_in_hours * 3600)

    with closing(db_connection()) as conn:
        conn.execute(
            """
            INSERT INTO invites (token, wizarr_invite_url, email, status, created_at, expires_at)
            VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (token, wizarr_invite, email, created_at, expires_at),
        )
        conn.commit()

    return {
        "token": token,
        "status": "pending",
        "created_at": created_at,
        "expires_at": expires_at,
        "invite_url": invite_url(token),
        "wizarr_invite_url": wizarr_invite,
    }


def render_page(title: str, body_html: str, status_code: int = 200) -> Response:
    content = f"""
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #0b1220;
      --bg-2: #1a2238;
      --card: #111a2e;
      --text: #e6edf8;
      --muted: #9fb0c9;
      --accent: #1d9bf0;
      --accent-2: #0ea5a5;
      --border: #2a3957;
      --ok: #22c55e;
      --warn: #f59e0b;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      background: radial-gradient(circle at top right, #182641 0%, var(--bg) 55%);
      color: var(--text);
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 20px;
    }}
    .card {{
      width: 100%;
      max-width: 640px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 18px 50px rgba(0, 0, 0, 0.45);
      padding: 28px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 1.6rem;
    }}
    .eyebrow {{
      font-size: 0.83rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 10px;
      font-weight: 600;
    }}
    p {{
      margin: 0 0 14px;
      color: var(--muted);
      line-height: 1.45;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }}
    .btn {{
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      font-weight: 600;
      text-decoration: none;
      display: inline-block;
      cursor: pointer;
      background: var(--accent);
      color: #ffffff;
    }}
    .btn[disabled] {{
      cursor: not-allowed;
      opacity: 0.5;
      pointer-events: none;
    }}
    .btn.success {{
      background: var(--ok);
    }}
    .btn.secondary {{
      background: #374a6a;
    }}
    .mono {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.9rem;
      color: #d7e2f3;
      background: #16213a;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px;
      overflow-wrap: anywhere;
    }}
    .status {{
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 12px;
      margin: 0 0 14px;
      font-size: 0.95rem;
      color: var(--text);
      background: #121d33;
    }}
    .status.ok {{
      border-color: #1e7a46;
      background: #10261a;
    }}
    .status.warn {{
      border-color: #7a5a1e;
      background: #2a1f0d;
    }}
  </style>
</head>
<body>
  <main class=\"card\">
    {body_html}
  </main>
</body>
</html>
"""
    return Response(content, status=status_code, mimetype="text/html")


@app.before_request
def setup() -> None:
    init_db()


@app.get("/healthz")
def healthz() -> Response:
    return Response(status=204)


@app.get("/health")
def health() -> Response:
    return jsonify({"status": "ok"}), 200


@app.post("/api/admin/invites")
def create_invite() -> tuple[Response, int] | tuple[dict, int]:
    if not require_admin_key():
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    wizarr_invite = (data.get("wizarr_invite_url") or "").strip()
    email = (data.get("email") or "").strip() or None
    expires_in_hours = data.get("expires_in_hours", INVITE_TOKEN_TTL_HOURS)

    if not is_valid_url(wizarr_invite):
        return jsonify({"error": "wizarr_invite_url must be a valid http(s) URL"}), 400

    try:
        expires_in_hours = int(expires_in_hours)
    except (TypeError, ValueError):
        return jsonify({"error": "expires_in_hours must be an integer"}), 400

    if expires_in_hours < 1 or expires_in_hours > 720:
        return jsonify({"error": "expires_in_hours must be between 1 and 720"}), 400

    payload = create_broker_invite_record(wizarr_invite, email, expires_in_hours)
    return jsonify(payload), 201


@app.post("/api/admin/flow-invites")
def create_flow_invite() -> tuple[Response, int] | tuple[dict, int]:
    if not require_admin_key():
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip() or None
    expires_in_hours = data.get("expires_in_hours", INVITE_TOKEN_TTL_HOURS)

    try:
        expires_in_hours = int(expires_in_hours)
    except (TypeError, ValueError):
        return jsonify({"error": "expires_in_hours must be an integer"}), 400

    if expires_in_hours < 1 or expires_in_hours > 720:
        return jsonify({"error": "expires_in_hours must be between 1 and 720"}), 400

    try:
        wizarr_invite = create_wizarr_invite(data)
    except Exception as exc:
        return jsonify({"error": f"failed_to_create_wizarr_invite: {exc}"}), 502

    payload = create_broker_invite_record(wizarr_invite, email, expires_in_hours)
    payload["auto_generated"] = True
    return jsonify(payload), 201


@app.get("/api/admin/invites/<token>")
def get_invite_status(token: str) -> tuple[Response, int] | Response:
    if not require_admin_key():
        return jsonify({"error": "unauthorized"}), 401

    row = get_invite(token)
    if row is None:
        return jsonify({"error": "not_found"}), 404

    payload = {
        "token": row["token"],
        "status": row["status"],
        "email": row["email"],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "activated_at": row["activated_at"],
        "pocket_id_completed_at": row["pocket_id_completed_at"],
        "invite_url": invite_url(row["token"]),
        "wizarr_invite_url": row["wizarr_invite_url"],
        "activation_url": row["activation_url"],
        "signup_token_id": row["signup_token_id"],
        "last_error": row["last_error"],
    }
    return jsonify(payload)


@app.get("/i/<token>")
def invite_landing(token: str) -> Response:
    row = refresh_invite_completion(token)
    if row is None:
        return render_page("Invite not found", "<h1>Invite not found</h1><p>This invite link does not exist.</p>", 404)

    if row["expires_at"] <= now_ts():
        return render_page(
            "Invite expired",
            "<h1>Invite expired</h1><p>This invite has expired. Ask the admin for a new one.</p>",
            410,
        )

    if not row["activation_url"]:
        try:
            activation_url, signup_token_id = create_pocket_signup_link()
            with closing(db_connection()) as conn:
                conn.execute(
                    """
                    UPDATE invites
                    SET status = 'activation_link_generated', activated_at = ?, activation_url = ?, signup_token_id = ?, pocket_id_completed_at = NULL, last_error = NULL
                    WHERE token = ?
                    """,
                    (now_ts(), activation_url, signup_token_id, token),
                )
                conn.commit()
            row = refresh_invite_completion(token)
        except Exception as exc:
            return render_page(
                "Activation failed",
                (
                    "<h1>Could not generate Pocket ID activation link</h1>"
                    "<p>Try again in a few moments or contact the admin.</p>"
                    f"<p class=\"mono\">{html.escape(str(exc))}</p>"
                ),
                502,
            )

    if row is None or not row["activation_url"]:
        return render_page(
            "Activation failed",
            "<h1>Could not prepare activation link</h1><p>Please contact the admin.</p>",
            502,
        )

    activation_url = html.escape(row["activation_url"])
    actions: list[str] = []
    heading = f"You've been invited to join {html.escape(INVITE_SERVER_NAME)}"
    intro = f"<h1>{heading}</h1>"

    actions.append(f'<a class="btn" href="{activation_url}" target="_blank" rel="noopener">Activate Pocket ID</a>')

    if row["pocket_id_completed_at"]:
        actions.append(f'<a class="btn success" href="/i/{token}/continue">Continue</a>')
        status = '<p class="status ok">Pocket ID activation detected. You can continue.</p>'
    else:
        actions.append('<button class="btn secondary" type="button" disabled>Continue</button>')
        status = '<p class="status warn">Activate Pocket ID first, then continue to the server onboarding.</p>'

    info = (
        intro
        + "<p>Before you start the onboarding, you must set up your Pocket ID account so we can securely grant you access to the server.</p>"
        + status
    )

    body = info + f'<div class="actions">{"".join(actions)}</div>'
    return render_page("Invite onboarding", body)


@app.post("/i/<token>/activate")
def activate_invite(token: str) -> Response:
    row = get_invite(token)
    if row is None:
        return render_page("Invite not found", "<h1>Invite not found</h1><p>This invite link does not exist.</p>", 404)

    if row["expires_at"] <= now_ts():
        return render_page(
            "Invite expired",
            "<h1>Invite expired</h1><p>This invite has expired. Ask the admin for a new one.</p>",
            410,
        )

    if row["activation_url"]:
        return redirect(f"/i/{token}", code=303)

    try:
        activation_url, signup_token_id = create_pocket_signup_link()
    except Exception as exc:
        with closing(db_connection()) as conn:
            conn.execute(
                "UPDATE invites SET status = 'error', last_error = ? WHERE token = ?",
                (str(exc), token),
            )
            conn.commit()
        message = html.escape(str(exc))
        return render_page(
            "Activation failed",
            (
                "<h1>Could not generate Pocket ID activation link</h1>"
                "<p>Try again in a few moments or contact the admin.</p>"
                f"<p class=\"mono\">{message}</p>"
            ),
            502,
        )

    with closing(db_connection()) as conn:
        conn.execute(
            """
            UPDATE invites
            SET status = 'activation_link_generated', activated_at = ?, activation_url = ?, signup_token_id = ?, pocket_id_completed_at = NULL, last_error = NULL
            WHERE token = ?
            """,
            (now_ts(), activation_url, signup_token_id, token),
        )
        conn.commit()

    return redirect(f"/i/{token}", code=303)


@app.post("/i/<token>/verify")
def verify_pocket_id(token: str) -> Response:
    row = get_invite(token)
    if row is None:
        return render_page("Invite not found", "<h1>Invite not found</h1><p>This invite link does not exist.</p>", 404)

    if row["expires_at"] <= now_ts():
        return render_page(
            "Invite expired",
            "<h1>Invite expired</h1><p>This invite has expired. Ask the admin for a new one.</p>",
            410,
        )

    refresh_invite_completion(token)
    return redirect(f"/i/{token}", code=303)


@app.get("/i/<token>/continue")
def continue_to_wizarr(token: str) -> Response:
    row = refresh_invite_completion(token)
    if row is None:
        return render_page("Invite not found", "<h1>Invite not found</h1><p>This invite link does not exist.</p>", 404)

    if row["expires_at"] <= now_ts():
        return render_page(
            "Invite expired",
            "<h1>Invite expired</h1><p>This invite has expired. Ask the admin for a new one.</p>",
            410,
        )

    if not row["activation_url"]:
        return render_page(
            "Activation required",
            (
                "<h1>Activation required</h1>"
                "<p>You must generate and open the Pocket ID activation link first.</p>"
                f'<p><a class="btn" href="/i/{token}">Back to invite</a></p>'
            ),
            400,
        )

    if not row["pocket_id_completed_at"]:
        return render_page(
            "Pocket ID setup required",
            (
                "<h1>Pocket ID setup still pending</h1>"
                "<p>Finish Pocket ID setup, then confirm on the invite page to continue.</p>"
                f'<p><a class="btn" href="/i/{token}">Back to invite</a></p>'
            ),
            400,
        )

    return redirect(row["wizarr_invite_url"], code=302)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
