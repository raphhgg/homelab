import os
import logging
from flask import Flask, request, jsonify
import requests

from formatters import sonarr, radarr, autobrr

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

GOTIFY_URL = os.environ.get("GOTIFY_URL", "http://gotify:80")

TOKENS = {
    "sonarr": os.environ.get("SONARR_GOTIFY_TOKEN", ""),
    "radarr": os.environ.get("RADARR_GOTIFY_TOKEN", ""),
    "autobrr": os.environ.get("AUTOBRR_GOTIFY_TOKEN", ""),
}

FORMATTERS = {
    "sonarr": sonarr.format_webhook,
    "radarr": radarr.format_webhook,
    "autobrr": autobrr.format_webhook,
}


def send_to_gotify(token, title, message, priority, image_url=None):
    extras = {
        "client::display": {"contentType": "text/markdown"},
    }
    if image_url:
        extras["client::notification"] = {"bigImageUrl": image_url}

    resp = requests.post(
        f"{GOTIFY_URL}/message",
        headers={"X-Gotify-Key": token},
        json={
            "title": title,
            "message": message,
            "priority": priority,
            "extras": extras,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


@app.route("/webhook/<service>", methods=["POST"])
def webhook(service):
    formatter = FORMATTERS.get(service)
    if not formatter:
        log.warning("Unknown service: %s", service)
        return jsonify({"error": f"unknown service: {service}"}), 404

    token = TOKENS.get(service)
    if not token:
        log.warning("No Gotify token configured for %s", service)
        return jsonify({"error": f"no token for {service}"}), 500

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "invalid JSON"}), 400

    try:
        title, message, priority, image_url = formatter(payload)
    except Exception as e:
        log.exception("Formatter error for %s: %s", service, e)
        return jsonify({"error": str(e)}), 500

    try:
        send_to_gotify(token, title, message, priority, image_url)
        log.info("[%s] %s", service, title)
    except Exception as e:
        log.exception("Gotify send error for %s: %s", service, e)
        return jsonify({"error": str(e)}), 502

    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    configured = [s for s, t in TOKENS.items() if t]
    return jsonify({"status": "ok", "services": configured})
