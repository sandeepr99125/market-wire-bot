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

from formatter import get_summary

ALERTS_FILE = os.path.join(os.path.dirname(__file__), "alerts.json")
MAX_HISTORY = 200


def load_alerts():
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, "r") as f:
            return json.load(f)
    return []


def record_alert(entry, message, summary=None):
    """Appends one alert to the history file (newest first). summary
    can be precomputed (e.g. shared with format_alert's call) to avoid
    a redundant get_summary() call - pass None to have it computed here."""
    alerts = load_alerts()
    if summary is None:
        summary = get_summary(entry)

    alerts.insert(0, {
        "title": entry.get("title", "").strip(),
        "link": entry.get("link", "").strip(),
        "source": entry.get("source_feed", ""),
        "summary": summary,
        "message": message,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    })

    alerts = alerts[:MAX_HISTORY]

    with open(ALERTS_FILE, "w") as f:
        json.dump(alerts, f, indent=2)