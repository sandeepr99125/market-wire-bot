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
from collections import Counter
from datetime import datetime, timedelta, timezone

from config import TOPIC_KEYWORDS, BURST_WINDOW_MINUTES, MAX_ALERTS_PER_TOPIC_PER_WINDOW

SEEN_FILE = os.path.join(os.path.dirname(__file__), "seen_items.json")

TITLE_SIMILARITY_THRESHOLD = 0.82
RECENT_TITLES_WINDOW = 40

# Different outlets covering the identical underlying story often lead
# with different specific facts ("Oil heads for weekly gain..." vs
# "Oil edges lower, but heads for weekly gain..."), so their headlines
# can score well below TITLE_SIMILARITY_THRESHOLD on character-sequence
# matching even though they're the same news. Word-containment (what
# fraction of the shorter title's significant words also appear in the
# other) catches this - tested against real cross-source pairs, actual
# duplicates score 0.78-0.89 while topically-related-but-distinct
# stories score 0.14-0.40, so 0.7 sits comfortably between the two.
CONTENT_OVERLAP_THRESHOLD = 0.7

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_NUM_RE = re.compile(r"\d[\d,.]*")
_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "the", "as", "on", "in", "to", "for", "of", "and", "but",
    "is", "are", "after", "at", "with", "from", "over", "into", "amid", "its",
}


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


def _significant_words(title):
    return {w for w in _WORD_RE.findall(title.lower()) if w not in _STOPWORDS and len(w) > 2}


def _token_containment(title_a, title_b):
    """What fraction of the shorter title's significant words also
    appear in the other title - see CONTENT_OVERLAP_THRESHOLD."""
    words_a, words_b = _significant_words(title_a), _significant_words(title_b)
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / min(len(words_a), len(words_b))


def _titles_are_duplicates(title_a, title_b):
    """
    True if two titles look like the same underlying story - either
    the whole headline reads near-identical (character-sequence
    similarity), or they share most of the same significant words
    even if phrased differently (word-containment, see
    CONTENT_OVERLAP_THRESHOLD). Either signal alone is enough to call
    them "similar", but if either title cites specific numbers
    (prices, index levels, percentages), those numbers must then also
    match - otherwise same-template headlines like "Gold futures drop
    to ₹1,44,911/10g" on two different days (near-identical wording,
    but a different price) would be wrongly flagged as duplicates of
    each other.
    """
    norm_a, norm_b = _normalize_title(title_a), _normalize_title(title_b)
    seq_ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()

    looks_similar = (
        seq_ratio >= TITLE_SIMILARITY_THRESHOLD
        or _token_containment(title_a, title_b) >= CONTENT_OVERLAP_THRESHOLD
    )
    if not looks_similar:
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


def _classify_topic(title, summary=""):
    """Returns the first TOPIC_KEYWORDS bucket this text matches, or
    None if it doesn't fall into any of them - untopicked entries are
    never burst-capped, only ones we can actually group."""
    text = f"{title} {summary}".lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                return topic
    return None


def cap_topic_bursts(entries, recent_alerts, window_minutes=BURST_WINDOW_MINUTES,
                      max_per_topic=MAX_ALERTS_PER_TOPIC_PER_WINDOW):
    """
    During a fast-moving story, many genuinely distinct facts about
    the same underlying topic can each individually clear the
    relevance filter and pass dedupe_similar_titles (they're not
    near-duplicates of each other, just the same topic developing).
    This caps how many alerts on one topic go out within a rolling
    window - once the cap is hit, further same-topic entries are
    silently dropped for the rest of the window rather than flooding
    the channel with every incremental update. Counts against both
    recently posted alerts (recent_alerts) and earlier entries in
    this same batch, so the cap applies within a single run too.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

    topic_counts = Counter()
    for alert in recent_alerts:
        fetched_at = datetime.fromisoformat(alert["fetched_at"])
        if fetched_at >= cutoff:
            topic = _classify_topic(alert.get("title", ""), alert.get("summary", ""))
            if topic:
                topic_counts[topic] += 1

    kept = []
    for entry in entries:
        topic = _classify_topic(entry.get("title", ""), entry.get("summary", ""))
        if topic is None:
            kept.append(entry)
            continue
        if topic_counts[topic] >= max_per_topic:
            continue
        topic_counts[topic] += 1
        kept.append(entry)

    return kept
