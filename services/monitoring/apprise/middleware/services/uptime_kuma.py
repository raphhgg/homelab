"""
Uptime Kuma webhook transformer for Apprise Middleware.

Transforms Uptime Kuma webhook payloads into Apprise API-compatible format
with rich Discord notifications.
"""

from datetime import datetime
from flask import jsonify
import requests


def transform_payload(payload):
    """
    Transform Uptime Kuma webhook payload to Apprise API format.

    Args:
        payload (dict): Uptime Kuma webhook payload containing heartbeat, monitor, and msg

    Returns:
        dict: Apprise API-compatible payload with title, body, type, format, and tag
    """
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

    return apprise_payload, monitor_name, status_text


def handle_webhook(request, apprise_url, logger):
    """
    Handle Uptime Kuma webhook request.

    Args:
        request: Flask request object
        apprise_url: Apprise API base URL
        logger: Logger instance

    Returns:
        tuple: (response_dict, status_code)
    """
    try:
        # Get JSON payload from Uptime Kuma
        payload = request.get_json()

        if not payload:
            logger.warning("Received empty payload")
            return {"status": "error", "message": "Empty payload"}, 400

        logger.info(f"Received Uptime Kuma webhook payload: {payload}")

        # Transform payload
        apprise_payload, monitor_name, status_text = transform_payload(payload)

        # Forward to Apprise API
        apprise_endpoint = f"{apprise_url}/notify/uptime-kuma"
        logger.info(f"Forwarding notification to Apprise: {apprise_endpoint}")

        response = requests.post(
            apprise_endpoint,
            json=apprise_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        # Check Apprise response
        if response.status_code == 200:
            logger.info(f"Notification sent successfully for monitor '{monitor_name}' (status: {status_text})")
            return {
                "status": "success",
                "message": "Notification forwarded to Apprise"
            }, 200
        else:
            logger.error(f"Apprise returned error: {response.status_code} - {response.text}")
            return {
                "status": "error",
                "message": f"Apprise error: {response.status_code}"
            }, 502

    except requests.RequestException as e:
        logger.error(f"Failed to connect to Apprise: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to connect to Apprise: {str(e)}"
        }, 502

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Internal error: {str(e)}"
        }, 500
