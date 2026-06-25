"""
pendo.py - Server-side Pendo Track Event utility for analytics
"""

import json
import logging
import time
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

PENDO_TRACK_URL = "https://data.pendo.io/data/track"
PENDO_INTEGRATION_KEY = "7ed85287-fa54-4eef-b082-6d8afb739ed4"


def track(
    event: str,
    visitor_id: str = "system",
    account_id: str = "system",
    properties: dict[str, Any] | None = None,
) -> None:
    """Send a server-side track event to Pendo. Failures are logged and never raised."""
    payload = {
        "type": "track",
        "event": event,
        "visitorId": visitor_id,
        "accountId": account_id,
        "timestamp": int(time.time() * 1000),
    }
    if properties:
        payload["properties"] = properties

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            PENDO_TRACK_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-pendo-integration-key": PENDO_INTEGRATION_KEY,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
    except Exception:
        logger.debug("Failed to send Pendo track event: %s", event, exc_info=True)
