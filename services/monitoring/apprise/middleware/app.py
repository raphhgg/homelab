#!/usr/bin/env python3
"""
Apprise Middleware for Uptime Kuma and Beszel Notifications

This Flask service transforms webhook payloads from monitoring services into Apprise API-compatible format.
It creates rich Discord notifications with details extracted from the webhooks.

Routes:
    POST /webhook/uptime-kuma - Receive and transform Uptime Kuma webhooks
    POST /webhook/beszel - Receive and transform Beszel webhooks
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

# Import service-specific handlers
from services import uptime_kuma, beszel

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


@app.route("/webhook/uptime-kuma", methods=["POST"])
def uptime_kuma_webhook():
    """
    Receive Uptime Kuma webhook, transform payload, and forward to Apprise.

    Returns:
        JSON response with status and message
    """
    response_data, status_code = uptime_kuma.handle_webhook(request, APPRISE_URL, logger)
    return jsonify(response_data), status_code


@app.route("/webhook/beszel", methods=["POST"])
def beszel_webhook():
    """
    Receive Beszel webhook, transform payload, and forward to Apprise.

    Returns:
        JSON response with status and message
    """
    response_data, status_code = beszel.handle_webhook(request, APPRISE_URL, logger)
    return jsonify(response_data), status_code


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
        "version": "2.0.0",
        "description": "Transforms monitoring webhook payloads (Uptime Kuma, Beszel) to Apprise API format",
        "endpoints": {
            "POST /webhook/uptime-kuma": "Receive Uptime Kuma webhooks",
            "POST /webhook/beszel": "Receive Beszel webhooks",
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
