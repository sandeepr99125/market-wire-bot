"""
Digest layer: builds the once-daily morning (pre-market) and evening
(post-market) briefings, on top of the same per-item real-time alert
pipeline (feed_fetcher/filters/formatter). Unlike a real-time alert,
a digest looks at a whole time window at once and asks Claude to
synthesize a single prioritized briefing from it, rather than posting
one message per item.
"""

import re
from datetime import datetime, time, timedelta, timezone

from feed_fetcher import fetch_all_entries
from formatter import _client, ANTHROPIC_MODEL, _clean_summary
from storage import dedupe_similar_titles
from web_output import load_alerts

IST = timezone(timedelta(hours=5, minutes=30))

# NSE session boundaries, IST. Only accounts for weekends, not market
# holidays (Diwali, Republic Day, etc.) - a holiday morning digest
# will look back to the prior calendar weekday's close rather than
# the true last trading session. Known simplification.
_MARKET_OPEN = time(9, 15)
_MARKET_CLOSE = time(15, 30)

_SHARED_RULES = (
    "Discard anything that doesn't meet the high-impact bar - this is a "
    "curated briefing, not a headline dump. Assume most items in the batch "
    "should be left out. Include only: government/regulatory policy, "
    "FII/DII flows, mutual fund flows, geopolitics with a market "
    "read-through, statements from global policymakers (Fed/ECB/BoJ/US "
    "Treasury/etc) that touch tariffs, trade, or risk sentiment, inflation "
    "data, jobs data, infrastructure/capex announcements, interest rate "
    "decisions, commodities (crude/gold/silver/metals) with sector "
    "read-through, and INR/USD currency moves large enough to matter. "
    "Exclude single-stock news unless the stock is a Nifty50/Sensex "
    "constituent or the move is a market-wide talking point, routine "
    "brokerage notes, and anything already covered elsewhere in this batch "
    "(keep only the most complete version).\n\n"
    "Each section can be 2-4 sentences, synthesizing across sources rather "
    "than restating one headline. Omit a section's line entirely if "
    "nothing in the batch meets the bar for it - don't pad with filler. "
    "If nothing in the whole batch clears the bar, respond with exactly: "
    "NOTHING"
)

_MORNING_SYSTEM_PROMPT = (
    "You are a macro markets analyst preparing the pre-market WhatsApp "
    "briefing for Indian equity investors, covering the window from "
    "yesterday's market close to this morning. Tell the reader what "
    "happened overnight that will affect today's session, and what to "
    "watch during the day.\n\n"
    "Respond using EXACTLY this line format:\n"
    "GLOBAL: <how US markets closed, how Asia is trading, and the "
    "gap-up/gap-down bias for India's open - only if there's a clear "
    "signal>\n"
    "CATALYSTS: <key overnight catalysts - policy, FII/DII data, "
    "geopolitics, policymaker statements, inflation/jobs data, rate "
    "decisions - with reasoning, impact, and sectors/stocks affected>\n"
    "COMMODITIES: <overnight moves in crude, gold, silver, metals, "
    "INR/USD if material, with sector read-through>\n"
    "WATCH: <scheduled data releases or events today that could move "
    "markets, if known from the source items>\n\n" + _SHARED_RULES
)

_EVENING_SYSTEM_PROMPT = (
    "You are a macro markets analyst preparing the end-of-day WhatsApp "
    "wrap-up for Indian equity investors, covering today's session. Recap "
    "the day's real catalysts (not routine noise), explain what drove "
    "them and which sectors/stocks were affected, and flag what to watch "
    "overnight/tomorrow.\n\n"
    "Respond using EXACTLY this line format:\n"
    "CATALYSTS: <today's real catalysts - policy moves, FII/DII data, "
    "mutual fund flow data, geopolitics, policymaker statements, "
    "inflation/jobs data, rate decisions - with reasoning, impact, and "
    "sectors/stocks affected>\n"
    "FLOWS: <if today's provisional FII/DII net buy-sell data was "
    "reported, which sectors/stocks saw inflows vs outflows and the "
    "likely reason>\n"
    "COMMODITIES: <today's moves in crude, gold, silver, metals, INR/USD "
    "if material, with sector read-through>\n"
    "WATCH: <global events, data releases, or scheduled decisions that "
    "could set tomorrow's tone, if known from the source items>\n\n" + _SHARED_RULES
)

# (prefix, display label, icon)
_DIGEST_SECTIONS = {
    "morning": (
        ("GLOBAL:", "Global Markets Overnight", "🌏"),
        ("CATALYSTS:", "Key Overnight Catalysts", "📰"),
        ("COMMODITIES:", "Commodities & Currency", "🛢️"),
        ("WATCH:", "Watch Today", "👀"),
    ),
    "evening": (
        ("CATALYSTS:", "Day's Key Catalysts", "📰"),
        ("FLOWS:", "FII/DII Snapshot", "🏦"),
        ("COMMODITIES:", "Commodities & Currency", "🛢️"),
        ("WATCH:", "Overnight Watch", "🌙"),
    ),
}

_DIGEST_HEADING = {
    "morning": "🌅 *Morning Briefing*",
    "evening": "🌆 *Evening Wrap*",
}

MAX_BATCH_ITEMS = 120


def _previous_trading_day(d):
    """The most recent Mon-Fri before date d - weekends only, doesn't
    know about market holidays (see module docstring)."""
    d -= timedelta(days=1)
    while d.weekday() >= 5:  # Sat=5, Sun=6
        d -= timedelta(days=1)
    return d


def digest_window_start(mode, now_utc=None):
    """Returns the UTC datetime the digest should look back to."""
    now_utc = now_utc or datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(IST)

    if mode == "morning":
        start_date = _previous_trading_day(now_ist.date())
        start_ist = datetime.combine(start_date, _MARKET_CLOSE, tzinfo=IST)
    else:
        start_ist = datetime.combine(now_ist.date(), _MARKET_OPEN, tzinfo=IST)

    return start_ist.astimezone(timezone.utc)


def _entry_published_at(entry):
    parsed = entry.get("published_parsed")
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _entry_in_window(entry, window_start_utc):
    # Entries with no parseable published time are excluded rather
    # than included-by-default - a malformed pubDate shouldn't let a
    # stale item sneak into the digest as if it were fresh.
    published = _entry_published_at(entry)
    return published is not None and published >= window_start_utc


def _gather_batch(mode, window_start_utc):
    """Combines already-flagged alerts in the window with a fresh raw
    RSS fetch covering the same window, deduped against each other.
    The raw fetch is NOT run through filters.is_relevant() - the
    digest prompt does its own high-impact judgment over a wider net,
    since an item that didn't clear the real-time per-item bar alone
    might still be worth a mention alongside other overnight context."""
    flagged = [a for a in load_alerts() if datetime.fromisoformat(a["fetched_at"]) >= window_start_utc]
    flagged_titles = [a["title"] for a in flagged]

    raw_entries = fetch_all_entries()
    raw_in_window = [e for e in raw_entries if _entry_in_window(e, window_start_utc)]
    fresh_raw = dedupe_similar_titles(raw_in_window, flagged_titles)

    items = [
        {"source": a.get("source", ""), "title": a.get("title", ""), "summary": a.get("summary", "")}
        for a in flagged
    ]
    items += [
        {
            "source": e.get("source_feed", ""),
            "title": e.get("title", "").strip(),
            "summary": _clean_summary(e.get("summary", ""), e.get("title", "")),
        }
        for e in fresh_raw
    ]

    return items[:MAX_BATCH_ITEMS]


def _parse_digest(text, mode):
    """Parses the GLOBAL:/CATALYSTS:/COMMODITIES:/WATCH: (or evening
    equivalent) sections into a labeled, WhatsApp-formatted block -
    same convention as formatter._parse_structured_summary, but each
    section can span multiple sentences, so this matches non-greedily
    up to the next known prefix rather than splitting by line."""
    sections = _DIGEST_SECTIONS[mode]
    prefixes = [p for p, _label, _icon in sections]
    alternation = "|".join(re.escape(p) for p in prefixes)
    pattern = re.compile(r"(" + alternation + r")\s*(.*?)(?=" + alternation + r"|\Z)", re.DOTALL)

    found = {}
    for match in pattern.finditer(text):
        prefix, body = match.group(1), match.group(2).strip()
        if body:
            found[prefix] = body

    if not found:
        return ""

    blocks = [f"{icon} *{label}:* {found[prefix]}" for prefix, label, icon in sections if prefix in found]
    return "\n\n".join(blocks)


def _ai_digest(mode, items):
    """Returns "" on any failure (no API key, network error, response
    that doesn't match the expected format) - same never-break-the-run
    contract as formatter._ai_summary."""
    if not _client or not items:
        return ""

    listing = "\n".join(f"{i + 1}. [{it['source']}] {it['title']} — {it['summary']}" for i, it in enumerate(items))

    try:
        response = _client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=900,
            system=_MORNING_SYSTEM_PROMPT if mode == "morning" else _EVENING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"RSS batch ({len(items)} items):\n{listing}"}],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        if text.strip().upper() == "NOTHING":
            return ""
        return _parse_digest(text, mode)
    except Exception:
        return ""


def build_digest(mode):
    """Returns the formatted WhatsApp message for the given mode
    ("morning" or "evening"), or None if there's nothing to send
    (no API key configured, or nothing in the window cleared the bar)."""
    window_start_utc = digest_window_start(mode)
    items = _gather_batch(mode, window_start_utc)
    body = _ai_digest(mode, items)
    if not body:
        return None
    return f"{_DIGEST_HEADING[mode]}\n\n{body}"
