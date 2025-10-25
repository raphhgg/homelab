"""
Service-specific webhook transformers for Apprise Middleware.

Each service module provides:
- transform_payload(payload): Transform service-specific webhook to Apprise format
- handle_webhook(request, apprise_url, logger): Handle incoming webhook and forward to Apprise
"""
