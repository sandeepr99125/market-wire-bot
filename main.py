"""
Orchestrator: wires the pipeline together.

    feed_fetcher -> filters -> storage (dedupe) -> formatter -> web_output

Each step lives in its own file (see the module list below). This
file just calls them in order - it shouldn't contain any actual
fetching/filtering/formatting logic itself.

run_once() (--mode=realtime, the default) no longer posts to WhatsApp
directly - it only fetches, filters, dedupes, and records each item to
the dashboard (alerts.json). Readers were getting one WhatsApp message
per item and it was too much volume to actually read. WhatsApp
delivery now happens exclusively through digest.py's hourly/morning/
evening consolidated updates (see run_digest()), which read back
what's been recorded here and synthesize it into one message instead
of one-per-item.

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
from digest import build_digest, is_weekly_digest_day, is_monthly_digest_day

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
    # a time.
    with ThreadPoolExecutor(max_workers=MAX_SUMMARY_WORKERS) as executor:
        summaries = list(executor.map(get_summary, new_entries))

    for entry, summary in zip(new_entries, summaries):
        message = format_alert(entry, summary=summary)
        record_alert(entry, message, summary=summary)


def run_digest(mode):
    print(f"[{datetime.now(timezone.utc).isoformat()}] Building {mode} digest...")

    message = build_digest(mode)
    if not message:
        print(f"No {mode} digest - nothing in the window cleared the bar.")
    else:
        post_alert(message)

    # Weekly/monthly piggyback on the existing evening/morning
    # schedule instead of needing their own separate cron-job.org
    # entries - the evening job already fires daily, so on Fridays it
    # also builds the weekly digest; the morning job already fires
    # daily, so on the 1st of the month it also builds the monthly one.
    if mode == "evening" and is_weekly_digest_day():
        run_digest("weekly")
    elif mode == "morning" and is_monthly_digest_day():
        run_digest("monthly")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", default="realtime",
        choices=["realtime", "hourly", "morning", "evening", "weekly", "monthly"],
    )
    args = parser.parse_args()

    if args.mode == "realtime":
        run_once()
    else:
        run_digest(args.mode)