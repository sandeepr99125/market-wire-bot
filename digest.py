"""
Digest layer: builds the once-daily morning (pre-market) and evening
(post-market) briefings, plus the rolling hourly consolidated update,
on top of the same real-time collection pipeline (feed_fetcher/
filters/formatter). A digest looks at a whole time window at once and
asks Claude to synthesize a single prioritized message from it, rather
than posting one message per item - the hourly mode is what
main.run_once() now relies on for actually reaching WhatsApp, since
individual items are recorded to the dashboard but no longer posted
one-by-one (see main.py).
"""

import re
from datetime import datetime, time, timedelta, timezone

from feed_fetcher import fetch_all_entries
from formatter import _client, ANTHROPIC_MODEL, _clean_summary
from market_data import fetch_sector_period_performance
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

_HOURLY_SYSTEM_PROMPT = (
    "You are a macro markets analyst preparing a rolling hourly WhatsApp "
    "update for Indian equity investors, covering roughly the last hour. "
    "Readers were previously getting one message per news item and it was "
    "too much noise to actually read - your job is to make sure nothing "
    "material gets missed, without spamming a separate message per item. "
    "Synthesize everything into one concise, readable update rather than "
    "listing items as disconnected facts.\n\n"
    "Respond using EXACTLY this line format:\n"
    "HEADLINE: <if one story clearly dominated the hour, name it in one "
    "line - omit this line entirely if nothing was dominant>\n"
    "UPDATES: <everything else material from the last hour, synthesized "
    "into a few sentences - group related items together and prioritize "
    "by impact rather than just listing headlines in order>\n"
    "WATCH: <anything scheduled or imminent worth flagging - omit if "
    "nothing specific>\n\n" + _SHARED_RULES
)

_SECTOR_INSTRUCTION = (
    "You'll be given the actual % move for each major Nifty sector index "
    "(Bank, IT, Metal, Auto, Pharma, FMCG, Energy, Realty, PSU Bank) over "
    "this period - use those real numbers, don't estimate or invent your "
    "own. Rank or group them by performance (leaders vs laggards) and "
    "explain what's driving the standout movers using the news batch (a "
    "policy shift, a commodity trend, an earnings theme, global cues) - "
    "don't just restate the numbers with no reason. Sectors with a small/"
    "flat move and no clear driver can be grouped together briefly."
)

_WEEKLY_SYSTEM_PROMPT = (
    "You are a macro markets analyst preparing a weekly WhatsApp wrap-up "
    "for Indian equity investors, covering the last 7 days. The focus is "
    "sector rotation - which sectors led, which lagged, and why - plus "
    "the week's real catalysts.\n\n"
    "Respond using EXACTLY this line format:\n"
    "SECTORS: <sector performance over the week and what drove it - " + _SECTOR_INSTRUCTION + ">\n"
    "CATALYSTS: <the week's real catalysts - policy moves, FII/DII/mutual "
    "fund flow trends, geopolitics, policymaker statements, inflation/"
    "jobs data, rate decisions - with reasoning, impact, and sectors/"
    "stocks affected>\n"
    "COMMODITIES: <the week's moves in crude, gold, silver, metals, "
    "INR/USD if material, with sector read-through>\n"
    "WATCH: <events, data releases, or decisions in the coming week that "
    "could set the tone, if known from the source items>\n\n" + _SHARED_RULES
)

_MONTHLY_SYSTEM_PROMPT = (
    "You are a macro markets analyst preparing a monthly WhatsApp wrap-up "
    "for Indian equity investors, covering the last 30 days. The focus is "
    "sector rotation over the month - which sectors led, which lagged, "
    "and the broader macro themes that shaped the month, not routine "
    "day-to-day noise.\n\n"
    "Respond using EXACTLY this line format:\n"
    "SECTORS: <sector performance over the month and what drove it - " + _SECTOR_INSTRUCTION + ">\n"
    "CATALYSTS: <the month's defining catalysts and themes - policy "
    "moves, FII/DII/mutual fund flow trends, geopolitics, policymaker "
    "statements, inflation/jobs data, rate decisions - with reasoning, "
    "impact, and sectors/stocks affected. Prioritize themes that played "
    "out over multiple weeks over single-day events>\n"
    "COMMODITIES: <the month's moves in crude, gold, silver, metals, "
    "INR/USD if material, with sector read-through>\n"
    "WATCH: <events, data releases, or decisions in the coming month "
    "that could set the tone, if known from the source items>\n\n" + _SHARED_RULES
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
    "hourly": (
        ("HEADLINE:", "This Hour", "⚡"),
        ("UPDATES:", "Updates", "📰"),
        ("WATCH:", "Watch", "👀"),
    ),
    "weekly": (
        ("SECTORS:", "Sector Rotation This Week", "📊"),
        ("CATALYSTS:", "Week's Key Catalysts", "📰"),
        ("COMMODITIES:", "Commodities & Currency", "🛢️"),
        ("WATCH:", "Watch Next Week", "👀"),
    ),
    "monthly": (
        ("SECTORS:", "Sector Rotation This Month", "📊"),
        ("CATALYSTS:", "Month's Defining Themes", "📰"),
        ("COMMODITIES:", "Commodities & Currency", "🛢️"),
        ("WATCH:", "Watch Next Month", "👀"),
    ),
}

_DIGEST_HEADING = {
    "morning": "🌅 *Morning Briefing*",
    "evening": "🌆 *Evening Wrap*",
    "hourly": "🕐 *Hourly Update*",
    "weekly": "📅 *Weekly Wrap*",
    "monthly": "🗓️ *Monthly Wrap*",
}

_SYSTEM_PROMPTS = {
    "morning": _MORNING_SYSTEM_PROMPT,
    "evening": _EVENING_SYSTEM_PROMPT,
    "hourly": _HOURLY_SYSTEM_PROMPT,
    "weekly": _WEEKLY_SYSTEM_PROMPT,
    "monthly": _MONTHLY_SYSTEM_PROMPT,
}

# Yahoo Finance range parameter for each mode's sector-performance
# lookback - only weekly/monthly show sector data (see
# _sector_period_snapshot_text). Modes absent from this dict get no
# sector block at all.
_SECTOR_RANGE = {
    "weekly": "5d",
    "monthly": "1mo",
}

MAX_BATCH_ITEMS = 120
WEEKLY_WINDOW_DAYS = 7
MONTHLY_WINDOW_DAYS = 30


def _previous_trading_day(d):
    """The most recent Mon-Fri before date d - weekends only, doesn't
    know about market holidays (see module docstring)."""
    d -= timedelta(days=1)
    while d.weekday() >= 5:  # Sat=5, Sun=6
        d -= timedelta(days=1)
    return d


HOURLY_WINDOW_MINUTES = 60


def digest_window_start(mode, now_utc=None):
    """Returns the UTC datetime the digest should look back to."""
    now_utc = now_utc or datetime.now(timezone.utc)

    if mode == "hourly":
        # A simple rolling window, not tied to market open/close - the
        # hourly digest runs throughout the active window (see the
        # cron-job.org schedule), not just around market hours.
        return now_utc - timedelta(minutes=HOURLY_WINDOW_MINUTES)

    if mode == "weekly":
        return now_utc - timedelta(days=WEEKLY_WINDOW_DAYS)

    if mode == "monthly":
        # A rolling 30 days, not calendar-month-aligned - simpler than
        # tracking "1st of the month" and avoids a short first digest
        # if triggered mid-month.
        return now_utc - timedelta(days=MONTHLY_WINDOW_DAYS)

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


def _sector_period_snapshot_text(range_param):
    """Formats sector index performance over the given Yahoo range
    ("5d" for weekly, "1mo" for monthly) as a plain-text line for the
    digest prompt - e.g. "Bank -3.3%, IT -2.37%, Metal +0.26%". This
    is a fresh live fetch each call (not persisted), since it's only
    needed at digest-build time. Returns "" on total fetch failure."""
    performance = fetch_sector_period_performance(range_param)
    parts = []
    for data in performance.values():
        change_pct = data["change_pct"]
        sign = "+" if change_pct >= 0 else ""
        label = data["label"].removeprefix("Nifty ")
        parts.append(f"{label} {sign}{change_pct}%")
    return ", ".join(parts)


def _ai_digest(mode, items):
    """Returns "" on any failure (no API key, network error, response
    that doesn't match the expected format) - same never-break-the-run
    contract as formatter._ai_summary."""
    if not _client or not items:
        return ""

    listing = "\n".join(f"{i + 1}. [{it['source']}] {it['title']} — {it['summary']}" for i, it in enumerate(items))

    sector_block = ""
    if mode in _SECTOR_RANGE:
        sector_snapshot = _sector_period_snapshot_text(_SECTOR_RANGE[mode])
        if sector_snapshot:
            sector_block = (
                f"\n\nNifty sector index moves over this period (real data, "
                f"use these exact numbers): {sector_snapshot}"
            )

    try:
        response = _client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=900,
            system=_SYSTEM_PROMPTS[mode],
            messages=[{"role": "user", "content": f"RSS batch ({len(items)} items):\n{listing}{sector_block}"}],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        if text.strip().upper() == "NOTHING":
            return ""
        return _parse_digest(text, mode)
    except Exception:
        return ""


def is_weekly_digest_day(now_utc=None):
    """True on the day the weekly digest should also run, piggybacked
    on the evening job instead of needing its own cron-job.org entry -
    Friday, right after the week's last trading close."""
    now_ist = (now_utc or datetime.now(timezone.utc)).astimezone(IST)
    return now_ist.weekday() == 4  # Monday=0 ... Friday=4


def is_monthly_digest_day(now_utc=None):
    """True on the day the monthly digest should also run, piggybacked
    on the morning job instead of needing its own cron-job.org entry -
    the 1st of the month."""
    now_ist = (now_utc or datetime.now(timezone.utc)).astimezone(IST)
    return now_ist.day == 1


def build_digest(mode):
    """Returns the formatted WhatsApp message for the given mode
    ("morning", "evening", "hourly", "weekly", or "monthly"), or None
    if there's nothing to send (no API key configured, or nothing in
    the window cleared the bar).

    For weekly/monthly, the SECTORS data is always accurate - it's a
    fresh Yahoo Finance fetch of the real period-over-period move, not
    dependent on our own history. The CATALYSTS section is best-effort
    only, though: RSS feeds only carry the last day or two of items,
    and _gather_batch's other source (alerts.json) is capped at
    web_output.MAX_HISTORY (200) entries, which recent daily alert
    volume can exhaust well within a 7-30 day window. So a weekly/
    monthly catalysts recap will tend to be recency-biased toward the
    end of the window rather than a complete recap of the whole
    period - a known limitation, not a bug.
    """
    window_start_utc = digest_window_start(mode)
    items = _gather_batch(mode, window_start_utc)
    body = _ai_digest(mode, items)
    if not body:
        return None
    return f"{_DIGEST_HEADING[mode]}\n\n{body}"
