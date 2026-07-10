"""
Tests for the relevance-matching logic in filters.py, including a
regression test for a real bug found in production: plain substring
matching let short keywords like "war" match inside unrelated words
like "award" ("arbitral awards"). Word-boundary matching fixed it.
"""

from filters import is_relevant


def test_relevant_when_watchlist_name_present():
    assert is_relevant("Donald Trump comments on trade", "") is True


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
