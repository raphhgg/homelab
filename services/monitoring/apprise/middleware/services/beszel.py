"""
Beszel webhook transformer for Apprise Middleware.

Transforms Beszel webhook payloads into Apprise API-compatible format.
All alerts are marked as critical (red) since Beszel only sends alerts
when configured thresholds are exceeded.
"""

import requests


def transform_payload(payload):
    """
    Transform Beszel webhook payload to Apprise API format.

    Args:
        payload (dict): Beszel webhook payload containing title and message

    Returns:
        tuple: (apprise_payload, title, severity) - Apprise payload dict, alert title, and severity level
    """
    # Extract data from Beszel payload
    # Beszel sends: {"title": "Alert name", "message": "Alert details"}
    title = payload.get("title", "Beszel Alert")
    message = payload.get("message", "No details provided")

    # All Beszel alerts are critical (red) since they only trigger when thresholds are exceeded
    apprise_type = "failure"
    severity_emoji = "🔴"
    severity = "critical"

    # Create formatted title with emoji
    formatted_title = f"{severity_emoji} {title}"

    # Build rich markdown body
    body = f"{message}"

    # Create Apprise payload
    apprise_payload = {
        "title": formatted_title,
        "body": body,
        "type": apprise_type,
        "format": "markdown",
        "tag": ["beszel", severity]
    }

    return apprise_payload, title, severity


def handle_webhook(request, apprise_url, logger):
    """
    Handle Beszel webhook request.

    Args:
        request: Flask request object
        apprise_url: Apprise API base URL
        logger: Logger instance

    Returns:
        tuple: (response_dict, status_code)
    """
    try:
        # Get JSON payload from Beszel
        payload = request.get_json()

        if not payload:
            logger.warning("Received empty payload from Beszel")
            return {"status": "error", "message": "Empty payload"}, 400

        logger.info(f"Received Beszel webhook payload: {payload}")

        # Transform payload
        apprise_payload, title, severity = transform_payload(payload)

        # Forward to Apprise API
        apprise_endpoint = f"{apprise_url}/notify/beszel"
        logger.info(f"Forwarding notification to Apprise: {apprise_endpoint}")

        response = requests.post(
            apprise_endpoint,
            json=apprise_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        # Check Apprise response
        if response.status_code == 200:
            logger.info(f"Notification sent successfully for alert '{title}' (severity: {severity})")
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
        logger.error(f"Error processing Beszel webhook: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Internal error: {str(e)}"
        }, 500
