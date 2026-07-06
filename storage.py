"""
Storage layer: remembers which entries we've already processed,
so re-running the script doesn't re-post the same alert.

Uses a simple JSON file for now - swap this for a real database
(SQLite, etc.) later if the list grows large or you deploy to a
platform with an ephemeral filesystem.
"""

import json
import os

SEEN_FILE = os.path.join(os.path.dirname(__file__), "seen_items.json")


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
