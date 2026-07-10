"""
Tests for the summary-cleaning and message-building logic in
formatter.py. These exercise only the deterministic, offline pieces
(_clean_summary, _truncate, format_alert with a precomputed summary)
- nothing here calls the real Claude API, so tests stay fast and free
regardless of whether ANTHROPIC_API_KEY is set in the environment.
"""

import formatter
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


def test_format_alert_uses_precomputed_summary_not_title(monkeypatch):
    # _shorten_link makes a real network call - stub it so this test
    # stays fast, free, and deterministic like the rest of the suite.
    monkeypatch.setattr(formatter, "_shorten_link", lambda url: url)

    entry = {
        "title": "Gold price falls",
        "link": "https://example.com/a",
        "source_feed": "Test Source",
    }
    message = format_alert(entry, summary="Gold fell due to a stronger dollar.")
    # The title is intentionally NOT repeated when a summary exists -
    # WhatsApp's own preview card already shows it, so repeating it
    # here would be the exact redundancy this format is meant to avoid.
    assert "Gold fell due to a stronger dollar." in message
    assert "https://example.com/a" in message
    assert "Gold price falls" not in message


def test_format_alert_falls_back_to_title_when_summary_empty(monkeypatch):
    monkeypatch.setattr(formatter, "_shorten_link", lambda url: url)

    entry = {
        "title": "Gold price falls",
        "link": "https://example.com/a",
        "source_feed": "Test Source",
    }
    message = format_alert(entry, summary="")
    # With no summary, the title is the fallback so the message never
    # ships empty even if the preview card fails to render.
    assert "Gold price falls" in message
    assert message.count("\n\n") == 1


def test_shorten_link_falls_back_to_original_on_failure(monkeypatch):
    def _raise(*args, **kwargs):
        raise ConnectionError("network unavailable")

    monkeypatch.setattr(formatter.requests, "get", _raise)
    original = "https://example.com/some/very/long/article/path"
    assert formatter._shorten_link(original) == original


def test_shorten_link_returns_empty_for_empty_url():
    assert formatter._shorten_link("") == ""
