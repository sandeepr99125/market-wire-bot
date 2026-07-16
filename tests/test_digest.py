"""
Tests for the deterministic parts of digest.py: the trading-window
computation (including the weekend-skipping regression it's built
for - a Monday morning digest must look back to Friday's close, not
Sunday) and the section parser. The Claude call itself (_ai_digest)
isn't tested here, same as formatter._ai_summary - it needs a live
API key and its failure mode (return "") is already the safe default.
"""

from datetime import datetime, timezone

from digest import digest_window_start, _parse_digest


def test_morning_window_looks_back_to_previous_days_close():
    # Tuesday 2026-07-14 08:00 IST -> Monday 2026-07-13 15:30 IST close
    now_utc = datetime(2026, 7, 14, 2, 30, tzinfo=timezone.utc)  # 08:00 IST
    start = digest_window_start("morning", now_utc)
    assert start == datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc)  # Mon 15:30 IST


def test_monday_morning_window_skips_weekend_to_friday():
    # Monday 2026-07-20 08:00 IST -> Friday 2026-07-17 15:30 IST close,
    # not Sunday - this is the regression this function exists for.
    now_utc = datetime(2026, 7, 20, 2, 30, tzinfo=timezone.utc)  # 08:00 IST Monday
    start = digest_window_start("morning", now_utc)
    assert start == datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)  # Fri 15:30 IST


def test_evening_window_starts_at_todays_market_open():
    # Tuesday 2026-07-14 16:30 IST -> today 09:15 IST open
    now_utc = datetime(2026, 7, 14, 11, 0, tzinfo=timezone.utc)  # 16:30 IST
    start = digest_window_start("evening", now_utc)
    assert start == datetime(2026, 7, 14, 3, 45, tzinfo=timezone.utc)  # 09:15 IST


def test_parse_digest_builds_labeled_block_for_morning():
    raw = (
        "GLOBAL: US markets closed higher on rate-cut hopes; Asia trading mixed.\n"
        "CATALYSTS: RBI held the repo rate steady, citing sticky inflation. This "
        "keeps borrowing costs unchanged for now.\n"
        "COMMODITIES: Crude slipped 2% on ceasefire talk.\n"
        "WATCH: US CPI print due this evening."
    )
    result = _parse_digest(raw, "morning")
    assert "🌏 *Global Markets Overnight:* US markets closed higher" in result
    assert "📰 *Key Overnight Catalysts:* RBI held the repo rate steady" in result
    assert "🛢️ *Commodities & Currency:* Crude slipped 2%" in result
    assert "👀 *Watch Today:* US CPI print due this evening." in result
    assert result.count("\n\n") == 3


def test_parse_digest_omits_missing_sections():
    raw = "CATALYSTS: Fed held rates steady."
    result = _parse_digest(raw, "morning")
    assert result == "📰 *Key Overnight Catalysts:* Fed held rates steady."
    assert "Global" not in result


def test_parse_digest_handles_multi_sentence_sections_without_bleeding():
    # A section can span several sentences - must not swallow the next
    # section's prefix into the previous section's body.
    raw = (
        "CATALYSTS: FIIs bought Rs 2,000 crore. Banking and IT led inflows. "
        "This reversed a two-day selling streak.\n"
        "FLOWS: DIIs were net sellers today.\n"
        "COMMODITIES: Gold flat.\n"
        "WATCH: Fed minutes tomorrow."
    )
    result = _parse_digest(raw, "evening")
    assert "reversed a two-day selling streak." in result
    assert "FLOWS:" not in result  # raw prefix shouldn't leak into the body
    assert "🏦 *FII/DII Snapshot:* DIIs were net sellers today." in result


def test_parse_digest_returns_empty_when_no_sections_found():
    assert _parse_digest("Nothing structured here.", "morning") == ""
