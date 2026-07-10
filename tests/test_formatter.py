"""
Tests for the summary-cleaning and message-building logic in
formatter.py. These exercise only the deterministic, offline pieces
(_clean_summary, _truncate, format_alert with a precomputed summary)
- nothing here calls the real Claude API, so tests stay fast and free
regardless of whether ANTHROPIC_API_KEY is set in the environment.
"""

from formatter import _clean_summary, _truncate, format_alert, SUMMARY_MAX_LEN


def test_strips_html_tags_and_entities():
    raw = "<p>Oil prices <b>jumped</b> 5%, said the report.</p>"
    result = _clean_summary(raw, title="Oil prices surge")
    assert "<" not in result and ">" not in result
    assert "jumped" in result


def test_strips_boilerplate_trailer():
    raw = "Analysts expect continued momentum in the sector. Read more at example.com"
    result = _clean_summary(raw, title="Market update today")
    assert "read more" not in result.lower()
    assert "Analysts expect continued momentum" in result


def test_empty_when_summary_duplicates_title():
    title = "Sensex falls over 680 points"
    result = _clean_summary(title, title)
    assert result == ""


def test_empty_when_too_short_after_cleaning():
    result = _clean_summary("- Reuters", title="Some headline")
    assert result == ""


def test_strips_title_prefix_when_summary_starts_with_it():
    title = "Elon Musk comments on tariffs"
    raw = "Elon Musk comments on tariffs - and it moved markets significantly today"
    result = _clean_summary(raw, title)
    assert not result.lower().startswith(title.lower())
    assert "moved markets" in result


def test_empty_when_raw_summary_is_falsy():
    assert _clean_summary("", title="Anything") == ""
    assert _clean_summary(None, title="Anything") == ""


def test_truncate_leaves_short_text_unchanged():
    text = "Short summary."
    assert _truncate(text) == text


def test_truncate_cuts_long_text_at_word_boundary():
    text = "word " * 100
    result = _truncate(text)
    assert len(result) <= SUMMARY_MAX_LEN + 1  # +1 for the ellipsis character
    assert result.endswith("…")
    assert not result[:-1].endswith(" ")  # trailing space stripped before ellipsis


def test_format_alert_includes_precomputed_summary():
    entry = {
        "title": "Gold price falls",
        "link": "https://example.com/a",
        "source_feed": "Test Source",
    }
    message = format_alert(entry, summary="Gold fell due to a stronger dollar.")
    assert "Gold price falls" in message
    assert "Gold fell due to a stronger dollar." in message
    assert "https://example.com/a" in message
    assert "Test Source" in message


def test_format_alert_omits_summary_block_when_empty():
    entry = {
        "title": "Gold price falls",
        "link": "https://example.com/a",
        "source_feed": "Test Source",
    }
    message = format_alert(entry, summary="")
    # Only two blocks (header, footer) joined by "\n\n" - no middle summary block
    assert message.count("\n\n") == 1
