"""
Tests for the ID-based and title-similarity dedup logic in
storage.py, including a regression test for a real false-positive
risk found before shipping: same-template daily headlines like
"Gold futures drop to ₹1,44,911/10g" scored highly on text similarity
across different days/prices, so a naive threshold would have wrongly
suppressed legitimate new price updates.
"""

from datetime import datetime, timedelta, timezone

from storage import dedupe_entries, dedupe_similar_titles, cap_topic_bursts, MAX_ALERTS_PER_TOPIC_PER_WINDOW


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


def _alert(title, minutes_ago):
    return {
        "title": title,
        "summary": "",
        "fetched_at": (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat(),
    }


def test_cap_topic_bursts_drops_once_topic_cap_reached():
    # MAX_ALERTS_PER_TOPIC_PER_WINDOW gold alerts already posted
    # recently - one more gold entry should be dropped.
    recent = [_alert(f"Gold futures move to Rs {i}/10g", minutes_ago=10) for i in range(MAX_ALERTS_PER_TOPIC_PER_WINDOW)]
    entries = [{"title": "Gold prices edge higher on safe-haven demand", "link": "new"}]
    result = cap_topic_bursts(entries, recent)
    assert result == []


def test_cap_topic_bursts_keeps_entry_under_the_cap():
    recent = [_alert("Gold futures move to Rs 1/10g", minutes_ago=10)]  # only 1, cap not reached
    entries = [{"title": "Gold prices edge higher on safe-haven demand", "link": "new"}]
    result = cap_topic_bursts(entries, recent)
    assert len(result) == 1


def test_cap_topic_bursts_ignores_alerts_outside_the_window():
    # These are old enough to be outside BURST_WINDOW_MINUTES, so they
    # shouldn't count toward the cap.
    recent = [_alert(f"Gold futures move to Rs {i}/10g", minutes_ago=120) for i in range(MAX_ALERTS_PER_TOPIC_PER_WINDOW)]
    entries = [{"title": "Gold prices edge higher on safe-haven demand", "link": "new"}]
    result = cap_topic_bursts(entries, recent)
    assert len(result) == 1


def test_cap_topic_bursts_does_not_cross_contaminate_different_topics():
    # A burst of gold alerts shouldn't cap an unrelated crude oil entry.
    recent = [_alert(f"Gold futures move to Rs {i}/10g", minutes_ago=10) for i in range(MAX_ALERTS_PER_TOPIC_PER_WINDOW)]
    entries = [{"title": "Crude oil rises on supply concerns", "link": "new"}]
    result = cap_topic_bursts(entries, recent)
    assert len(result) == 1


def test_cap_topic_bursts_applies_within_a_single_batch_too():
    # No recent history, but the batch itself contains more same-topic
    # entries than the cap allows - later ones in the batch should
    # still be dropped once the running count hits the cap.
    entries = [{"title": f"Gold prices move to Rs {i}/10g on demand", "link": str(i)} for i in range(MAX_ALERTS_PER_TOPIC_PER_WINDOW + 2)]
    result = cap_topic_bursts(entries, recent_alerts=[])
    assert len(result) == MAX_ALERTS_PER_TOPIC_PER_WINDOW


def test_cap_topic_bursts_never_caps_untopicked_entries():
    recent = [_alert(f"Gold futures move to Rs {i}/10g", minutes_ago=10) for i in range(MAX_ALERTS_PER_TOPIC_PER_WINDOW)]
    entries = [{"title": "Union Budget hikes GST council allocation for infrastructure", "link": "new"}]
    result = cap_topic_bursts(entries, recent)
    assert len(result) == 1
