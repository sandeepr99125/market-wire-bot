"""
Tests for the summary-cleaning and message-building logic in
formatter.py. These exercise only the deterministic, offline pieces
(_clean_summary, _truncate, format_alert with a precomputed summary)
- nothing here calls the real Claude API, so tests stay fast and free
regardless of whether ANTHROPIC_API_KEY is set in the environment.
"""

from formatter import _clean_summary, _truncate, _parse_structured_summary, format_alert, SUMMARY_MAX_LEN


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
    text = "word " * 200  # comfortably longer than SUMMARY_MAX_LEN
    result = _truncate(text)
    assert len(result) <= SUMMARY_MAX_LEN + 1  # +1 for the ellipsis character
    assert result.endswith("…")
    assert not result[:-1].endswith(" ")  # trailing space stripped before ellipsis


def test_format_alert_uses_precomputed_summary_not_title():
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
    # The direct link, no shortener - avoids an extra redirect hop.
    assert "https://example.com/a" in message
    assert "Gold price falls" not in message


def test_format_alert_falls_back_to_title_when_summary_empty():
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


def test_parse_structured_summary_builds_labeled_block_with_icons():
    raw = (
        "WHAT: Oil prices rose 3% today.\n"
        "IMPACT: Higher input costs for oil-importing economies.\n"
        "REASON: Iran tensions are choking Strait of Hormuz shipping."
    )
    result = _parse_structured_summary(raw)
    assert "*Market Alert:* Oil prices rose 3% today." in result
    assert "💥 *Impact:* Higher input costs for oil-importing economies." in result
    assert "💡 *Reason:* Iran tensions are choking Strait of Hormuz shipping." in result
    # Each section on its own line, blank line between
    assert result.count("\n\n") == 2


def test_parse_structured_summary_is_case_insensitive_on_prefix():
    raw = "what: A thing happened.\nimpact: It mattered.\nreason: Because reasons."
    result = _parse_structured_summary(raw)
    assert "*Market Alert:* A thing happened." in result


def test_parse_structured_summary_omits_impact_and_reason_when_not_written():
    # Impact/Reason are optional - Claude is instructed to skip them
    # rather than pad with filler when they don't add real analysis.
    raw = "WHAT: A minor administrative filing was made."
    result = _parse_structured_summary(raw)
    assert result == "*Market Alert:* A minor administrative filing was made."
    assert "Impact" not in result
    assert "Reason" not in result


def test_parse_structured_summary_keeps_impact_without_reason():
    raw = "WHAT: Oil prices rose.\nIMPACT: Costs went up for importers."
    result = _parse_structured_summary(raw)
    assert "*Market Alert:* Oil prices rose." in result
    assert "💥 *Impact:* Costs went up for importers." in result
    assert "Reason" not in result


def test_parse_structured_summary_includes_sector_stock_line():
    raw = (
        "WHAT: RBI held the repo rate steady.\n"
        "SECTOR: Banking — HDFC Bank\n"
        "IMPACT: Positive for lenders' net interest margins.\n"
        "REASON: Unchanged rates preserve current lending spreads."
    )
    result = _parse_structured_summary(raw)
    assert "📊 *Sector/Stock:* Banking — HDFC Bank" in result
    # Ordered: What, Sector, Impact, Reason
    assert result.index("Sector/Stock") < result.index("Impact")
    assert result.index("Impact") < result.index("Reason")


def test_parse_structured_summary_omits_sector_when_not_written():
    # Not every story names a specific sector/stock - SECTOR is
    # optional the same way IMPACT/REASON are.
    raw = "WHAT: A minor administrative filing was made."
    result = _parse_structured_summary(raw)
    assert "Sector" not in result


def test_parse_structured_summary_empty_when_required_line_missing():
    raw = "IMPACT: Costs went up.\nREASON: Because reasons."  # no WHAT line
    assert _parse_structured_summary(raw) == ""


def test_parse_structured_summary_empty_on_freeform_text():
    raw = "Oil prices rose today because of tensions in the Middle East."
    assert _parse_structured_summary(raw) == ""
