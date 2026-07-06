"""
Web output layer: records alerts to a JSON file so the dashboard
(index.html) can display them.

This is deliberately separate from storage.py (which just tracks
"have we seen this" for dedup) - this file keeps the actual alert
content, capped to a reasonable history size for the page to show.
"""

import json
import os
from datetime import datetime, timezone

ALERTS_FILE = os.path.join(os.path.dirname(__file__), "alerts.json")
MAX_HISTORY = 200


def load_alerts():
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, "r") as f:
            return json.load(f)
    return []


def record_alert(entry, message):
    """Appends one alert to the history file (newest first)."""
    alerts = load_alerts()

    alerts.insert(0, {
        "title": entry.get("title", "").strip(),
        "link": entry.get("link", "").strip(),
        "source": entry.get("source_feed", ""),
        "message": message,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    })

    alerts = alerts[:MAX_HISTORY]

    with open(ALERTS_FILE, "w") as f:
        json.dump(alerts, f, indent=2)