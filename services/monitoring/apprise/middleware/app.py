#!/usr/bin/env python3
"""
Apprise Middleware for Uptime Kuma Notifications

This Flask service transforms Uptime Kuma webhook payloads into Apprise API-compatible format.
It creates rich Discord notifications with monitor details extracted from the webhook.

Routes:
    POST /webhook/uptime-kuma - Receive and transform Uptime Kuma webhooks
    GET /health - Health check endpoint for monitoring

Environment:
    APPRISE_URL - Apprise API base URL (default: http://apprise:8000)
    LOG_LEVEL - Logging level (default: INFO)
"""

import logging
import os
import sys
from datetime import datetime
from flask import Flask, request, jsonify
import requests

# Initialize Flask app
app = Flask(__name__)

# Configuration
APPRISE_URL = os.getenv("APPRISE_URL", "http://apprise:8000")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def transform_uptime_kuma_payload(payload):
    """
    Transform Uptime Kuma webhook payload to Apprise API format.

    Args:
        payload (dict): Uptime Kuma webhook payload containing heartbeat, monitor, and msg

    Returns:
        dict: Apprise API-compatible payload with title, body, type, format, and tag
    """
    try:
        # Extract data from Uptime Kuma payload
        heartbeat = payload.get("heartbeat") or {}
        monitor = payload.get("monitor") or {}
        msg = payload.get("msg", "")

        # Extract monitor details (with safety checks for None)
        monitor_name = monitor.get("name", "Unknown Monitor") if monitor else "Unknown Monitor"
        monitor_type = monitor.get("type", "unknown") if monitor else "unknown"
        monitor_url = (monitor.get("url") or monitor.get("hostname") or "N/A") if monitor else "N/A"

        # Extract heartbeat details
        status = heartbeat.get("status")
        error_msg = heartbeat.get("msg", "")
        duration = heartbeat.get("duration", 0)
        # Use localDateTime instead of time (UTC) to show timezone-aware timestamp
        timestamp = heartbeat.get("localDateTime") or heartbeat.get("time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # Determine status and emoji
        if status == 1:
            status_emoji = "🟢"
            status_text = "UP"
            apprise_type = "success"
        elif status == 0:
            status_emoji = "🔴"
            status_text = "DOWN"
            apprise_type = "failure"
        else:
            status_emoji = "🟡"
            status_text = "UNKNOWN"
            apprise_type = "warning"

        # Create title
        title = f"{status_emoji} {monitor_name} is {status_text}"

        # Build rich markdown body
        body_parts = [
            f"**Status:** {status_text}",
            f"**Monitor:** {monitor_name}",
            f"**Type:** {monitor_type.upper()}",
        ]

        # Add URL/hostname if available
        if monitor_url and monitor_url != "N/A":
            body_parts.append(f"**URL:** {monitor_url}")

        # Add error message if present (for DOWN status)
        if error_msg and status == 0:
            body_parts.append(f"**Error:** {error_msg}")

        # Add duration
        if duration > 0:
            body_parts.append(f"**Duration:** {duration}ms")

        # Add timestamp
        body_parts.append(f"**Time:** {timestamp}")

        # Join all parts with newlines
        body = "\n".join(body_parts)

        # Create Apprise payload
        apprise_payload = {
            "title": title,
            "body": body,
            "type": apprise_type,
            "format": "markdown",
            "tag": "uptime-kuma"
        }

        logger.info(f"Transformed payload for monitor '{monitor_name}' (status: {status_text})")
        return apprise_payload

    except Exception as e:
        logger.error(f"Error transforming payload: {e}", exc_info=True)
        raise


@app.route("/webhook/uptime-kuma", methods=["POST"])
def uptime_kuma_webhook():
    """
    Receive Uptime Kuma webhook, transform payload, and forward to Apprise.

    Returns:
        JSON response with status and message
    """
    try:
        # Get JSON payload from Uptime Kuma
        payload = request.get_json()

        if not payload:
            logger.warning("Received empty payload")
            return jsonify({"status": "error", "message": "Empty payload"}), 400

        logger.info(f"Received Uptime Kuma webhook payload: {payload}")

        # Transform payload
        apprise_payload = transform_uptime_kuma_payload(payload)

        # Forward to Apprise API
        apprise_endpoint = f"{APPRISE_URL}/notify/uptime-kuma"
        logger.info(f"Forwarding notification to Apprise: {apprise_endpoint}")

        response = requests.post(
            apprise_endpoint,
            json=apprise_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        # Check Apprise response
        if response.status_code == 200:
            logger.info("Notification sent to Apprise successfully")
            return jsonify({
                "status": "success",
                "message": "Notification forwarded to Apprise"
            }), 200
        else:
            logger.error(f"Apprise returned error: {response.status_code} - {response.text}")
            return jsonify({
                "status": "error",
                "message": f"Apprise error: {response.status_code}"
            }), 502

    except requests.RequestException as e:
        logger.error(f"Failed to connect to Apprise: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Failed to connect to Apprise: {str(e)}"
        }), 502

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Internal error: {str(e)}"
        }), 500


@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint for monitoring.

    Returns:
        JSON response with health status
    """
    return jsonify({
        "status": "healthy",
        "service": "apprise-middleware",
        "timestamp": datetime.now().isoformat()
    }), 200


@app.route("/", methods=["GET"])
def index():
    """
    Root endpoint with service information.

    Returns:
        JSON response with service details
    """
    return jsonify({
        "service": "Apprise Middleware",
        "version": "1.0.0",
        "description": "Transforms Uptime Kuma webhook payloads to Apprise API format",
        "endpoints": {
            "POST /webhook/uptime-kuma": "Receive Uptime Kuma webhooks",
            "GET /health": "Health check endpoint",
            "GET /": "Service information"
        }
    }), 200


if __name__ == "__main__":
    logger.info("Starting Apprise Middleware...")
    logger.info(f"Apprise URL: {APPRISE_URL}")
    logger.info(f"Log Level: {LOG_LEVEL}")

    # Run Flask app
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=(LOG_LEVEL == "DEBUG")
    )
