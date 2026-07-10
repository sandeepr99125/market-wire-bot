"""
Tests for the relevance-matching logic in filters.py, including
regression tests for real noise found in production: plain substring
matching let short keywords like "war" match inside unrelated words
like "award" ("arbitral awards") - fixed with word-boundary matching.
Later, broadening to global feeds (BBC, Al Jazeera) let through
unrelated personal news about watchlist people (Trump's son's crypto
bets), plain war/casualty reporting with no market angle, and
individual-company stock stories (Kalyan Jewellers, Vedanta) that
happened to mention a commodity in passing - fixed with the
context-required and single-stock-exclusion rules below.
"""

from filters import is_relevant


def test_relevant_when_watchlist_person_has_context():
    assert is_relevant("Donald Trump comments on trade", "") is True


def test_not_relevant_when_watchlist_person_has_no_market_context():
    # Real noise: mentions a watchlist name but is personal/unrelated
    # news, not anything that moves Indian markets.
    title = "Donald Trump's son bet big on Bitcoin, lost $600 million from family fortune"
    assert is_relevant(title, "") is False


def test_not_relevant_when_watchlist_person_tesla_crash_has_no_context():
    title = "Not just Elon Musk; retail investors are losing money in Tesla and SpaceX crash"
    assert is_relevant(title, "") is False


def test_relevant_when_watchlist_institution_alone():
    # Institutions are inherently economic news - no context required.
    assert is_relevant("IMF cuts India's growth forecast to 6.3%", "") is True


def test_relevant_when_market_keyword_present():
    assert is_relevant("Gold prices rise sharply", "") is True


def test_not_relevant_when_neither_name_nor_keyword_present():
    assert is_relevant("Local bakery wins award for best bread", "") is False


def test_word_boundary_prevents_false_positive_on_award():
    # "war" must not match inside "award" / "awards"
    title = "Delhi High Court clears enforcement of $99 million in arbitral awards"
    assert is_relevant(title, "") is False


def test_word_boundary_prevents_false_positive_on_arbitral():
    # "rbi" must not match inside "arbitral"
    title = "Court ruling on arbitral proceedings between two firms"
    assert is_relevant(title, "") is False


def test_word_boundary_still_matches_real_war_keyword():
    assert is_relevant("Russia-Ukraine war disrupts supply chains", "") is True


def test_word_boundary_still_matches_real_rbi_keyword():
    assert is_relevant("RBI holds repo rate steady", "") is True


def test_matches_in_summary_not_just_title():
    assert is_relevant("Markets today", "Crude oil prices surged overnight") is True


def test_geopolitical_keyword_relevant_with_economic_context():
    # War impacting the economy - exactly what should get through.
    title = "Crude oil futures gain on reports of Iranian strikes on US military targets"
    assert is_relevant(title, "") is True


def test_geopolitical_keyword_not_relevant_without_economic_context():
    # Plain war/casualty reporting (common on global feeds like Al
    # Jazeera/BBC) with no bearing on Indian markets.
    title = "Russian attacks kill four as Ukraine continues strikes"
    assert is_relevant(title, "") is False


def test_sector_keyword_relevant_alone():
    assert is_relevant("Metal stocks rally as China stimulus lifts demand", "") is True


def test_single_stock_move_excluded_even_with_keyword_match():
    # Real noise: individual jeweller's stock price move, not gold
    # market news, even though "gold" appears in the summary.
    title = "Kalyan Jewellers shares jump 9%, extend two-day rally to over 15%"
    summary = "Gold prices have been volatile this quarter."
    assert is_relevant(title, summary) is False


def test_single_stock_move_excluded_mcap_phrasing():
    title = "Kalyan Jewellers jumps 9%, m-cap swells by Rs 13,280 crore in 3 days"
    assert is_relevant(title, "Gold demand rose this week.") is False


def test_single_company_oil_stock_excluded():
    title = "Vedanta Oil and Gas shares rally 8% on strong output"
    assert is_relevant(title, "") is False


def test_broad_market_move_not_excluded_by_stock_move_check():
    # "Sensex jumps" describes the whole index, not a single company -
    # must not be caught by the single-stock exclusion.
    assert is_relevant("Sensex jumps over 600 points, Nifty reclaims 24,000", "") is True


def test_sector_hit_skips_single_stock_exclusion():
    # "Bank stocks" is sector-wide phrasing even though it contains
    # the word "stocks" - shouldn't be excluded as a single-stock move.
    title = "Bank nifty stocks rally as RBI holds rates"
    assert is_relevant(title, "") is True


def test_past_tense_stock_move_excluded():
    title = "Multibaggers: 13 stocks surged up to 225% in just 3 months"
    assert is_relevant(title, "Gold and silver stocks led gains.") is False


def test_brokerage_buy_call_excluded():
    # Real noise: single-stock analyst target-price note, exactly the
    # content type moneycontrol's dead feed used to be full of.
    title = "Nuvama initiates Buy call on Vedanta Aluminium shares, expects profitability to exceed historical average"
    assert is_relevant(title, "Aluminium prices have been rising this quarter.") is False


def test_target_price_call_excluded():
    # Contains "gold" (a core keyword) so it would pass without the
    # brokerage-call exclusion - confirms the exclusion actually fires
    # rather than this just never matching a keyword to begin with.
    title = "Buy Titan Company; target of Rs 4,200 on strong gold jewellery demand: Motilal Oswal"
    assert is_relevant(title, "") is False


def test_top_gainers_listicle_excluded():
    title = "Top Gainers & Losers on 10 July: Godrej Industries, Indian Bank, Kalyan Jewellers among top gainers"
    assert is_relevant(title, "Gold prices steady.") is False
