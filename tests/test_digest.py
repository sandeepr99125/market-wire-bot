"""
Tests for the deterministic parts of digest.py: the trading-window
computation (including the weekend-skipping regression it's built
for - a Monday morning digest must look back to Friday's close, not
Sunday) and the section parser. The Claude call itself (_ai_digest)
isn't tested here, same as formatter._ai_summary - it needs a live
API key and its failure mode (return "") is already the safe default.
"""

from datetime import datetime, timezone

import digest
from digest import digest_window_start, _parse_digest, _sector_period_snapshot_text


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


def test_hourly_window_is_a_simple_rolling_hour():
    # Not tied to market open/close at all, unlike morning/evening -
    # just now minus 60 minutes, any day, any time.
    now_utc = datetime(2026, 7, 14, 11, 0, tzinfo=timezone.utc)
    start = digest_window_start("hourly", now_utc)
    assert start == datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc)


def test_hourly_window_works_on_a_weekend_unlike_morning_evening():
    # Sunday - morning/evening's weekend-aware logic doesn't apply
    # here, hourly just looks back exactly 60 minutes regardless.
    now_utc = datetime(2026, 7, 19, 8, 0, tzinfo=timezone.utc)  # Sunday
    start = digest_window_start("hourly", now_utc)
    assert start == datetime(2026, 7, 19, 7, 0, tzinfo=timezone.utc)


def test_weekly_window_is_a_rolling_7_days():
    now_utc = datetime(2026, 7, 20, 11, 0, tzinfo=timezone.utc)
    start = digest_window_start("weekly", now_utc)
    assert start == datetime(2026, 7, 13, 11, 0, tzinfo=timezone.utc)


def test_monthly_window_is_a_rolling_30_days():
    now_utc = datetime(2026, 7, 30, 11, 0, tzinfo=timezone.utc)
    start = digest_window_start("monthly", now_utc)
    assert start == datetime(2026, 6, 30, 11, 0, tzinfo=timezone.utc)


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
    assert "Sector" not in result  # morning no longer carries a sectors section


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


def test_parse_digest_builds_labeled_block_for_hourly():
    raw = (
        "HEADLINE: RBI held the repo rate steady at 6.5%.\n"
        "UPDATES: Rupee slipped 12 paise on dollar strength; crude edged "
        "up 1% on West Asia tensions.\n"
        "WATCH: US CPI print due tonight."
    )
    result = _parse_digest(raw, "hourly")
    assert "⚡ *This Hour:* RBI held the repo rate steady at 6.5%." in result
    assert "📰 *Updates:* Rupee slipped 12 paise" in result
    assert "👀 *Watch:* US CPI print due tonight." in result
    assert "Sector" not in result  # hourly no longer carries a sectors section


def test_parse_digest_hourly_omits_headline_when_nothing_dominant():
    raw = "UPDATES: A handful of minor sector updates, nothing dominant this hour."
    result = _parse_digest(raw, "hourly")
    assert result == "📰 *Updates:* A handful of minor sector updates, nothing dominant this hour."
    assert "This Hour" not in result


def test_parse_digest_builds_labeled_block_for_weekly():
    raw = (
        "SECTORS: Metals led the week, up 4% on China demand hopes; IT lagged, "
        "down 2% on weak US bookings.\n"
        "CATALYSTS: RBI held rates steady at the MPC meeting.\n"
        "COMMODITIES: Gold flat for the week.\n"
        "WATCH: US jobs report due Friday."
    )
    result = _parse_digest(raw, "weekly")
    assert "📊 *Sector Rotation This Week:* Metals led the week" in result
    assert "📰 *Week's Key Catalysts:* RBI held rates steady" in result
    assert "🛢️ *Commodities & Currency:* Gold flat for the week." in result
    assert "👀 *Watch Next Week:* US jobs report due Friday." in result


def test_parse_digest_builds_labeled_block_for_monthly():
    raw = (
        "SECTORS: Auto led the month on strong festive-season sales; Realty "
        "lagged on high rates.\n"
        "CATALYSTS: Fed cut rates 25bps mid-month, boosting EM flows.\n"
        "COMMODITIES: Crude rose 5% on OPEC+ supply cuts.\n"
        "WATCH: Union Budget expected next month."
    )
    result = _parse_digest(raw, "monthly")
    assert "📊 *Sector Rotation This Month:* Auto led the month" in result
    assert "📰 *Month's Defining Themes:* Fed cut rates 25bps" in result
    assert "👀 *Watch Next Month:* Union Budget expected next month." in result


def test_sector_period_snapshot_text_formats_real_data(monkeypatch):
    fake_performance = {
        "sector_bank": {"label": "Nifty Bank", "value": 56592.0, "change_pct": -3.3},
        "sector_it": {"label": "Nifty IT", "value": 28533.55, "change_pct": 5.63},
    }
    monkeypatch.setattr(digest, "fetch_sector_period_performance", lambda range_param: fake_performance)
    text = _sector_period_snapshot_text("1mo")
    assert "Bank -3.3%" in text
    assert "IT +5.63%" in text


def test_sector_period_snapshot_text_empty_on_total_failure(monkeypatch):
    monkeypatch.setattr(digest, "fetch_sector_period_performance", lambda range_param: {})
    assert _sector_period_snapshot_text("5d") == ""
