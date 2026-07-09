"""
Orchestrator: wires the pipeline together.

    feed_fetcher  -> filters  -> storage (dedupe) -> formatter -> poster

Each step lives in its own file (see the module list below). This
file just calls them in order - it shouldn't contain any actual
fetching/filtering/formatting logic itself.

Run with: uv run main.py
Dependencies are declared in pyproject.toml - uv reads that
automatically and installs anything missing before running.
"""

from datetime import datetime, timezone

from feed_fetcher import fetch_all_entries
from filters import filter_entries
from storage import load_seen, save_seen, dedupe_entries
from formatter import format_alert
from poster import post_alert
from web_output import record_alert
from market_data import fetch_market_kpis


def run_once():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Checking feeds...")

    fetch_market_kpis()

    all_entries = fetch_all_entries()
    relevant_entries = filter_entries(all_entries)

    seen_ids = load_seen()
    new_entries, updated_seen_ids = dedupe_entries(relevant_entries, seen_ids)
    save_seen(updated_seen_ids)

    if not new_entries:
        print("No new relevant items this run.")
        return

    print(f"Found {len(new_entries)} new relevant item(s):\n")
    for entry in new_entries:
        message = format_alert(entry)
        post_alert(message)
        record_alert(entry, message)


if __name__ == "__main__":
    run_once()