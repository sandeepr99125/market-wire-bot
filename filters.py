"""
Filtering layer: decides which entries are actually relevant.

Keeping this separate from fetching means you can tweak *what counts
as relevant* (smarter matching, an LLM call, sentiment scoring, etc.)
without touching how data gets fetched or posted.
"""

import re

from config import WATCHLIST_NAMES, MARKET_KEYWORDS

# Word-boundary matching, not plain substring - otherwise short terms
# like "war" or "rbi" match inside unrelated words ("award", "arbitral").
_NAME_PATTERNS = [re.compile(r"\b" + re.escape(name.lower()) + r"\b") for name in WATCHLIST_NAMES]
_KEYWORD_PATTERNS = [re.compile(r"\b" + re.escape(kw.lower()) + r"\b") for kw in MARKET_KEYWORDS]


def is_relevant(title, summary):
    """
    An entry is relevant if it mentions a watchlist name OR a
    macro/sector market-moving keyword. Either alone is enough -
    both lists are deliberately curated to broad-market movers, so
    a single hit is already a good signal (see config.py).
    """
    text = f"{title} {summary}".lower()

    name_hit = any(p.search(text) for p in _NAME_PATTERNS)
    keyword_hit = any(p.search(text) for p in _KEYWORD_PATTERNS)

    return name_hit or keyword_hit


def filter_entries(entries):
    """Takes raw entries, returns only the relevant ones."""
    relevant = []
    for entry in entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        if is_relevant(title, summary):
            relevant.append(entry)
    return relevant
