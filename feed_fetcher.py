"""
Fetching layer: talks to RSS feeds and returns raw entries.

If you ever swap RSS for a different data source (a paid tweet API,
a different news provider, etc.), this is the only file you'd need
to change - everything downstream just expects a list of entries
with title/summary/link/source_feed.
"""

import feedparser

from config import RSS_FEEDS


def fetch_all_entries():
    """
    Pulls every entry from every feed in config.RSS_FEEDS.
    Returns a flat list of feedparser entry objects, each tagged
    with which feed it came from.
    """
    all_entries = []

    for feed_url in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"[warn] couldn't fetch {feed_url}: {e}")
            continue

        if parsed.bozo:
            print(f"[warn] feed may be broken: {feed_url} ({parsed.bozo_exception})")

        feed_name = parsed.feed.get("title", feed_url)

        for entry in parsed.entries:
            entry["source_feed"] = feed_name
            all_entries.append(entry)

    return all_entries
