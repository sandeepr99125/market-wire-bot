"""
Filtering layer: decides which entries are actually relevant.

Keeping this separate from fetching means you can tweak *what counts
as relevant* (smarter matching, an LLM call, sentiment scoring, etc.)
without touching how data gets fetched or posted.
"""

import re

from config import (
    WATCHLIST_PEOPLE,
    WATCHLIST_INSTITUTIONS,
    CORE_KEYWORDS,
    SECTOR_KEYWORDS,
    GEOPOLITICAL_KEYWORDS,
    ECONOMIC_CONTEXT_KEYWORDS,
    NIFTY50_CONSTITUENTS,
)


def _patterns(words):
    # Word-boundary matching, not plain substring - otherwise short
    # terms like "war" or "rbi" match inside unrelated words ("award",
    # "arbitral").
    return [re.compile(r"\b" + re.escape(w.lower()) + r"\b") for w in words]


_PEOPLE_PATTERNS = _patterns(WATCHLIST_PEOPLE)
_INSTITUTION_PATTERNS = _patterns(WATCHLIST_INSTITUTIONS)
_CORE_PATTERNS = _patterns(CORE_KEYWORDS)
_SECTOR_PATTERNS = _patterns(SECTOR_KEYWORDS)
_GEO_PATTERNS = _patterns(GEOPOLITICAL_KEYWORDS)
_CONTEXT_PATTERNS = _patterns(ECONOMIC_CONTEXT_KEYWORDS)
_NIFTY50_PATTERNS = _patterns(NIFTY50_CONSTITUENTS)

# Individual-company share-price movement, e.g. "Kalyan Jewellers
# shares jump 9%" or "Vedanta stocks surge up to 6%" - this phrasing
# shows up constantly on Indian financial feeds and slips past the
# other filters because the story happens to mention a commodity/
# keyword in passing (a jeweller mentioning gold, an oil driller
# mentioning crude). It's single-stock noise, not the market-wide or
# sector-wide news the bot is meant to surface.
_MOVE_VERBS = (
    r"jump|jumps|jumped|rally|rallies|rallied|surge|surges|surged|"
    r"soar|soars|soared|zoom|zooms|zoomed|climb|climbs|climbed|"
    r"slump|slumps|slumped|tumble|tumbles|tumbled|crash|crashes|crashed|"
    r"gain|gains|gained|fall|falls|fell|rise|rises|rose|drop|drops|dropped|"
    r"in focus"
)
_STOCK_MOVE_RE = re.compile(
    r"\b(shares?|stocks?)\b[^.]{0,40}\b(" + _MOVE_VERBS + r")\b"
    r"|\bm-cap\b",
    re.IGNORECASE,
)
# ...unless the story is explicitly framed as market-wide, in which
# case a "shares rise" turn of phrase is describing the whole index,
# not one company.
_BROAD_MARKET_RE = re.compile(
    r"\b(sensex|nifty|benchmark|d-street|dalal street|broader market)\b",
    re.IGNORECASE,
)

# Single-stock brokerage notes ("Buy call on X; target of Rs Y",
# "Nuvama initiates Buy call on Vedanta Aluminium shares") - this was
# the entire content of the moneycontrol feed that got dropped for
# being stale, and it's exactly the individual stock-pick noise this
# bot is meant to filter out, regardless of which commodity/sector
# word the note happens to mention in passing. Always excluded - a
# brokerage target-price call is never legitimately market-wide.
_BROKERAGE_CALL_RE = re.compile(
    r"\b(buy|sell|accumulate|hold|add|reduce)\s+call\b"
    r"|\btarget (of|price)\b"
    r"|\binitiat(e|es|ed)\s+(coverage|buy|sell)\b"
    r"|\bstocks? to (buy|sell)\b"
    r"|\bshares? to (buy|sell)\b",
    re.IGNORECASE,
)

# Stock-picking listicles ("Multibaggers: 13 stocks surged up to
# 225%", "Top Gainers & Losers") - always excluded for the same
# reason as brokerage calls.
_LISTICLE_RE = re.compile(
    r"\bmultibaggers?\b|\btop gainers?\b|\btop losers?\b",
    re.IGNORECASE,
)

# Regulatory housekeeping against a bulk/unnamed group of small
# entities (RBI/SEBI cancelling registrations, resolving generic
# investor complaints) - real example that slipped through: "RBI
# cancels Certificate of Registration of 192 NBFCs". The affected
# party is a plural count of unnamed firms or generic "investors",
# never one specific listed stock or tradeable sector, so it always
# fails the "must be able to name a sector/stock" bar regardless of
# which other keyword the headline happens to also contain.
_UNNAMED_ENTITY_ACTION_RE = re.compile(
    r"\b(cancels?|cancelled|revokes?|revoked|bars?|barred)\b[^.]{0,60}"
    r"\b(registration|licen[cs]e|certificate)s?\b[^.]{0,30}\bof\s+\d+\b"
    r"|\bresolves?\b[^.]{0,40}\b(investors?|customers?)\b[^.]{0,40}\bcomplaints?\b",
    re.IGNORECASE,
)

# RBI's own press-release feed mixes genuine policy news (rate
# decisions, new circulars, named-entity actions) in with routine
# operational notices it publishes almost daily as standard
# housekeeping - VRR/repo auctions, money market operations, G-Sec
# conversions, SGB redemption prices. WATCHLIST_INSTITUTIONS lets any
# RBI mention through unconditionally since RBI statements are
# normally inherently market news, but these specific notices are
# routine plumbing, not "trade on this in the next hour" material -
# always excluded regardless of other keyword hits.
_ROUTINE_RBI_OPS_RE = re.compile(
    r"\bmoney market operations\b"
    r"|\b(variable rate repo|vrr)\b[^.]{0,20}\bauction\b"
    r"|\bunderwriting auction\b"
    r"|\bsovereign gold bond\b[^.]{0,40}\bredemption\b"
    r"|\bredemption price\b"
    r"|\bconversion\s*/\s*switch\b"
    r"|\bswitch of government (of india )?securities\b"
    r"|\bauction of[^.]{0,20}treasury bills\b"
    r"|\bcash management bills\b",
    re.IGNORECASE,
)


def _has_any(patterns, text):
    return any(p.search(text) for p in patterns)


def is_relevant(title, summary):
    """
    An entry is relevant if it's about something that actually moves
    Indian markets - not just anything that happens to contain a
    matching word. See config.py for how the keyword lists are split
    and why:

    - CORE_KEYWORDS / SECTOR_KEYWORDS / WATCHLIST_INSTITUTIONS: a hit
      alone is enough, these are already inherently market news.
    - WATCHLIST_PEOPLE / GEOPOLITICAL_KEYWORDS: a hit alone is NOT
      enough - these figures and war/conflict terms generate huge
      volumes of news with no market angle, so they only count when
      paired with an economic-context word.
    - Regardless of the above, a single company's share-price move
      (see _STOCK_MOVE_RE) is excluded unless it's explicitly framed
      as market-wide, and brokerage buy/sell calls, stock-picking
      listicles, and regulatory housekeeping against a bulk/unnamed
      group of small entities (see _BROKERAGE_CALL_RE / _LISTICLE_RE /
      _UNNAMED_ENTITY_ACTION_RE) are always excluded - none of these
      name a specific tradeable stock or sector, even when they
      mention a commodity or keyword in passing.
    """
    text = f"{title} {summary}".lower()

    core_hit = _has_any(_CORE_PATTERNS, text)
    sector_hit = _has_any(_SECTOR_PATTERNS, text)
    institution_hit = _has_any(_INSTITUTION_PATTERNS, text)
    nifty50_hit = _has_any(_NIFTY50_PATTERNS, text)
    has_context = core_hit or sector_hit or _has_any(_CONTEXT_PATTERNS, text)

    people_hit = _has_any(_PEOPLE_PATTERNS, text) and has_context
    geo_hit = _has_any(_GEO_PATTERNS, text) and has_context

    relevant = core_hit or sector_hit or institution_hit or people_hit or geo_hit
    if not relevant:
        return False

    if (
        _BROKERAGE_CALL_RE.search(text)
        or _LISTICLE_RE.search(text)
        or _UNNAMED_ENTITY_ACTION_RE.search(text)
        or _ROUTINE_RBI_OPS_RE.search(text)
    ):
        return False

    # A Nifty50 constituent's share-price move is still a market-wide
    # talking point (unlike a random small/mid-cap), same exemption as
    # a sector-wide hit.
    if not (sector_hit or nifty50_hit) and _STOCK_MOVE_RE.search(text) and not _BROAD_MARKET_RE.search(text):
        return False

    return True


def filter_entries(entries):
    """Takes raw entries, returns only the relevant ones."""
    relevant = []
    for entry in entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        if is_relevant(title, summary):
            relevant.append(entry)
    return relevant
