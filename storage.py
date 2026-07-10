"""
Storage layer: remembers which entries we've already processed,
so re-running the script doesn't re-post the same alert.

Uses a simple JSON file for now - swap this for a real database
(SQLite, etc.) later if the list grows large or you deploy to a
platform with an ephemeral filesystem.
"""

import difflib
import json
import os
import re

SEEN_FILE = os.path.join(os.path.dirname(__file__), "seen_items.json")

TITLE_SIMILARITY_THRESHOLD = 0.82
RECENT_TITLES_WINDOW = 40

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_NUM_RE = re.compile(r"\d[\d,.]*")


def load_seen():
    """Returns the set of entry IDs we've already processed."""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen_ids):
    """Persists the set of processed entry IDs to disk."""
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_ids), f)


def get_entry_id(entry):
    """A stable identifier for an entry - prefers the feed's own id."""
    return entry.get("id") or entry.get("link")


def dedupe_entries(entries, seen_ids):
    """
    Splits entries into (new_entries, all_ids_seen_this_run).
    new_entries excludes anything already in seen_ids.
    """
    new_entries = []
    all_ids = set(seen_ids)

    for entry in entries:
        entry_id = get_entry_id(entry)
        if not entry_id:
            continue
        if entry_id not in seen_ids:
            new_entries.append(entry)
        all_ids.add(entry_id)

    return new_entries, all_ids


def _normalize_title(title):
    return _PUNCT_RE.sub("", title.lower()).strip()


def _titles_are_duplicates(title_a, title_b):
    """
    True if two titles look like the same underlying story. Requires
    high text similarity, but if either title cites specific numbers
    (prices, index levels, percentages), those numbers must match too -
    otherwise same-template headlines like "Gold futures drop to
    ₹1,44,911/10g" on two different days (near-identical wording, but
    a different price) would be wrongly flagged as duplicates of each
    other.
    """
    norm_a, norm_b = _normalize_title(title_a), _normalize_title(title_b)
    if difflib.SequenceMatcher(None, norm_a, norm_b).ratio() < TITLE_SIMILARITY_THRESHOLD:
        return False

    nums_a, nums_b = frozenset(_NUM_RE.findall(title_a)), frozenset(_NUM_RE.findall(title_b))
    if nums_a or nums_b:
        return nums_a == nums_b

    return True


def dedupe_similar_titles(entries, recent_titles):
    """
    Drops entries whose title is a near-duplicate of one already seen -
    either an entry earlier in this same batch, or a recently posted
    alert. Different outlets often cover the same underlying story
    with the same or near-identical headline; each has its own unique
    link/id so it passes dedupe_entries(), but it's still the same
    news. Keeps the first occurrence encountered.
    """
    seen_titles = list(recent_titles[:RECENT_TITLES_WINDOW])
    kept = []

    for entry in entries:
        title = entry.get("title", "")
        if any(_titles_are_duplicates(title, other) for other in seen_titles):
            continue
        kept.append(entry)
        seen_titles.append(title)

    return kept
