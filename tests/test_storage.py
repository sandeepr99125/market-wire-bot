"""
Tests for the ID-based and title-similarity dedup logic in
storage.py, including a regression test for a real false-positive
risk found before shipping: same-template daily headlines like
"Gold futures drop to ₹1,44,911/10g" scored highly on text similarity
across different days/prices, so a naive threshold would have wrongly
suppressed legitimate new price updates.
"""

from storage import dedupe_entries, dedupe_similar_titles


def test_dedupe_entries_filters_already_seen():
    entries = [{"id": "a", "title": "One"}, {"id": "b", "title": "Two"}]
    new_entries, all_ids = dedupe_entries(entries, seen_ids={"a"})
    assert [e["id"] for e in new_entries] == ["b"]
    assert all_ids == {"a", "b"}


def test_dedupe_entries_uses_link_when_no_id():
    entries = [{"link": "https://x.com/1", "title": "One"}]
    new_entries, all_ids = dedupe_entries(entries, seen_ids=set())
    assert len(new_entries) == 1
    assert "https://x.com/1" in all_ids


def test_dedupe_entries_skips_entries_with_no_identifier():
    entries = [{"title": "No id or link"}]
    new_entries, all_ids = dedupe_entries(entries, seen_ids=set())
    assert new_entries == []
    assert all_ids == set()


def test_dedupe_similar_titles_catches_identical_duplicate_across_sources():
    entries = [
        {"title": "India's 10-year bond logs best day in over a week on oil relief", "link": "a"},
        {"title": "India's 10-year bond logs best day in over a week on oil relief", "link": "b"},
    ]
    result = dedupe_similar_titles(entries, recent_titles=[])
    assert len(result) == 1


def test_dedupe_similar_titles_keeps_same_template_different_price():
    # Regression test: these must NOT be treated as duplicates even
    # though they're near-identical text, because the price differs.
    entries = [{"title": "Gold futures drop to ₹1,44,911/10g", "link": "new"}]
    recent = ["Gold futures drop to ₹1,42,300/10g"]
    result = dedupe_similar_titles(entries, recent)
    assert len(result) == 1


def test_dedupe_similar_titles_keeps_genuinely_distinct_titles():
    entries = [
        {"title": "Sensex falls over 680 pts on crude spike", "link": "a"},
        {"title": "RBI holds repo rate steady amid inflation concerns", "link": "b"},
    ]
    result = dedupe_similar_titles(entries, recent_titles=[])
    assert len(result) == 2


def test_dedupe_similar_titles_checks_against_recent_history():
    entries = [{"title": "Fed signals rate cut in September", "link": "new"}]
    recent = ["Fed signals rate cut in September"]
    result = dedupe_similar_titles(entries, recent)
    assert result == []


def test_dedupe_similar_titles_catches_reworded_cross_source_duplicate():
    # Real pair from production: same underlying fact, different
    # outlets' phrasing. Character-sequence similarity alone (0.79)
    # falls just short of TITLE_SIMILARITY_THRESHOLD (0.82) - this
    # only gets caught via word-containment (0.78), which is the gap
    # this test locks in.
    entries = [{
        "title": "Oil edges lower, but heads for weekly gain as West Asia supply risks persist",
        "link": "new",
    }]
    recent = ["Oil heads for weekly gain as Middle East supply risks persist"]
    result = dedupe_similar_titles(entries, recent)
    assert result == []


def test_dedupe_similar_titles_keeps_distinct_stories_on_same_topic():
    # Both about the US-Iran situation, but different specific facts
    # (an IEA supply warning vs peace-talk prospects) - word overlap
    # is low (just "iran"), so these must NOT be merged even though
    # they'd cluster under the same alert category on the dashboard.
    entries = [{
        "title": "US-Iran escalation threatens oil supply recovery, warns IEA",
        "link": "new",
    }]
    recent = ["US-Iran war: Will peace talks resume, and when?"]
    result = dedupe_similar_titles(entries, recent)
    assert len(result) == 1


def test_dedupe_similar_titles_numeric_guard_applies_to_content_overlap_too():
    # Same regression as test_dedupe_similar_titles_keeps_same_template_different_price,
    # but confirms the numeric guard also protects the new
    # word-containment signal, not just the character-sequence one.
    entries = [{"title": "Gold futures drop to ₹1,44,911/10g", "link": "new"}]
    recent = ["Gold futures drop to ₹1,42,300/10g"]
    result = dedupe_similar_titles(entries, recent)
    assert len(result) == 1
