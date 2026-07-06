"""
Filtering layer: decides which entries are actually relevant.

Keeping this separate from fetching means you can tweak *what counts
as relevant* (smarter matching, an LLM call, sentiment scoring, etc.)
without touching how data gets fetched or posted.
"""

from config import WATCHLIST_NAMES, MARKET_KEYWORDS


def is_relevant(title, summary):
    """
    An entry is relevant if it mentions a watchlist name AND a
    market-related keyword. This two-part check keeps out noise
    (e.g. Musk tweeting about something with zero market angle).
    """
    text = f"{title} {summary}".lower()

    name_hit = any(name.lower() in text for name in WATCHLIST_NAMES)
    keyword_hit = any(kw.lower() in text for kw in MARKET_KEYWORDS)

    return name_hit and keyword_hit


def filter_entries(entries):
    """Takes raw entries, returns only the relevant ones."""
    relevant = []
    for entry in entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        if is_relevant(title, summary):
            relevant.append(entry)
    return relevant
