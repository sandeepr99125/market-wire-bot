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

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from feed_fetcher import fetch_all_entries
from filters import filter_entries
from storage import load_seen, save_seen, dedupe_entries, dedupe_similar_titles
from formatter import format_alert, get_summary
from poster import post_alert
from web_output import record_alert, load_alerts
from market_data import fetch_market_kpis
from digest import build_digest

MAX_SUMMARY_WORKERS = 5


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

    # Different outlets often cover the same story with the same or
    # near-identical headline - each has its own link/id so it passes
    # the check above, but it's still the same news.
    recent_titles = [a.get("title", "") for a in load_alerts()]
    new_entries = dedupe_similar_titles(new_entries, recent_titles)

    if not new_entries:
        print("No new relevant items this run (all were duplicates of recent alerts).")
        return

    print(f"Found {len(new_entries)} new relevant item(s):\n")

    # Each summary is an independent network call (feed cleanup or a
    # Claude API request) - fetch them concurrently instead of one at
    # a time, then reuse the same result for both the posted message
    # and the dashboard record instead of computing it twice.
    with ThreadPoolExecutor(max_workers=MAX_SUMMARY_WORKERS) as executor:
        summaries = list(executor.map(get_summary, new_entries))

    for entry, summary in zip(new_entries, summaries):
        message = format_alert(entry, summary=summary)
        post_alert(message)
        record_alert(entry, message, summary=summary)


def run_digest(mode):
    print(f"[{datetime.now(timezone.utc).isoformat()}] Building {mode} digest...")

    message = build_digest(mode)
    if not message:
        print(f"No {mode} digest - nothing in the window cleared the bar.")
        return

    post_alert(message)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="realtime", choices=["realtime", "morning", "evening"])
    args = parser.parse_args()

    if args.mode == "realtime":
        run_once()
    else:
        run_digest(args.mode)