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


def test_fii_dii_flow_relevant_alone():
    assert is_relevant("FIIs pour Rs 5,000 crore into Indian equities in June", "") is True


def test_mutual_fund_flow_relevant_alone():
    assert is_relevant("Equity mutual fund inflows hit record high in June: AMFI data", "") is True


def test_capex_relevant_alone():
    assert is_relevant("Government hikes capex allocation for railways in Budget", "") is True


def test_pmi_relevant_alone():
    assert is_relevant("India manufacturing PMI slips to 6-month low in June", "") is True


def test_credit_rating_action_relevant_alone():
    assert is_relevant("Moody's upgrades India's sovereign credit rating outlook", "") is True


def test_bare_rupee_relevant_alone():
    # Currency moves matter on their own, without needing an oil/Trump
    # mention to supply "context" - a real gap found before this fix.
    assert is_relevant("Rupee hits record low against dollar amid FII outflows", "") is True


def test_ecb_institution_relevant_alone():
    assert is_relevant("ECB holds rates steady, signals caution on inflation", "") is True


def test_boj_institution_relevant_alone():
    assert is_relevant("BoJ keeps ultra-loose policy unchanged despite yen weakness", "") is True


def test_bare_jobs_word_no_longer_sufficient_alone():
    # "jobs"/"employment"/"layoffs" mostly show up in single-company
    # hiring/firing headlines in Indian financial press, not macro
    # data releases - moved out of unconditional CORE_KEYWORDS.
    assert is_relevant("TechCorp announces fresh round of layoffs amid restructuring", "") is False


def test_macro_jobs_report_still_relevant():
    assert is_relevant("US jobs report beats expectations, payrolls surge", "") is True


def test_nifty50_constituent_stock_move_not_excluded():
    # A Nifty50 constituent's share-price move is still a market-wide
    # talking point, unlike a random small/mid-cap - exempted from the
    # single-stock exclusion the same way sector-wide hits are.
    title = "Reliance Industries shares jump 4% on strong Q1 earnings"
    assert is_relevant(title, "Oil refining margins improved this quarter.") is True


def test_non_nifty50_stock_move_still_excluded():
    title = "Kalyan Jewellers shares jump 9%, extend two-day rally to over 15%"
    assert is_relevant(title, "Gold prices have been volatile this quarter.") is False


def test_stocks_to_buy_recommendation_excluded():
    # Real noise: single-stock technical-analyst pick, doesn't contain
    # "target price" or "call" so the original brokerage regex missed it.
    title = "Stocks to buy: Nagaraj Shetti recommends LIC, RACL Geartech shares to buy in the short-term"
    assert is_relevant(title, "Gold prices steady, oil rises.") is False


def test_stocks_to_buy_or_sell_recommendation_excluded():
    title = "Stocks to buy or sell: Osho Krishan of Angel One suggests buying Aarti Industries shares"
    assert is_relevant(title, "Crude oil prices firm.") is False


def test_unnamed_bulk_registration_cancellation_excluded():
    # Real item that slipped through: no specific listed stock/sector
    # named, just a headcount of unnamed small NBFCs.
    title = "RBI cancels Certificate of Registration of 192 NBFCs"
    assert is_relevant(title, "") is False


def test_generic_investor_complaint_resolution_excluded():
    title = "SEBI resolves over 5,000 investors' complaints in June via SCORES platform"
    assert is_relevant(title, "") is False


def test_named_entity_registration_action_still_relevant():
    # Contrast case: a single named, numbered action (not a plural
    # headcount) should still pass through normally via other keywords.
    assert is_relevant("RBI approves appointment of Rajiv Kumar as chairman of HDFC Bank", "") is True


def test_vague_growth_context_no_longer_sufficient_for_watchlist_person():
    # "growth" alone names no specific tradeable sector - removed from
    # ECONOMIC_CONTEXT_KEYWORDS since it can't satisfy the "must name a
    # sector/stock" bar.
    title = "Narendra Modi meets business leaders to boost economic growth"
    assert is_relevant(title, "") is False


def test_trade_context_still_sufficient_for_watchlist_person():
    # "trade" stays - it ties to a concrete transmission mechanism
    # (trade-exposed sectors), unlike "growth"/"economy".
    assert is_relevant("Donald Trump comments on trade", "") is True
