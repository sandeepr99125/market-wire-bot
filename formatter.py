"""
Formatting layer: turns a raw entry into the text that gets posted.

Keeping this separate means the "how it looks" can change (add
emojis, change layout, add an AI-generated one-line summary instead
of the raw title) without touching fetching, filtering, or posting.
"""

import html
import os
import re

import anthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-haiku-4-5"

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

_AI_SYSTEM_PROMPT = (
    "You write one-sentence summaries of market news for a WhatsApp alert. "
    "Given a headline and a short excerpt, write exactly one concise sentence "
    "explaining what happened and why it matters to markets. Plain text only - "
    "no preamble, no quotation marks, no restating the headline verbatim."
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_BOILERPLATE_RE = re.compile(
    r"\b(read more|continue reading|also read|the post .* appeared first on)\b.*",
    re.IGNORECASE,
)

SUMMARY_MAX_LEN = 220
SUMMARY_MIN_LEN = 15


def _clean_summary(raw_summary, title):
    """Turns a raw, HTML-laden feed summary into clean display text,
    or "" if there's nothing worth showing (empty, a duplicate of the
    title, or just boilerplate/attribution cruft)."""
    if not raw_summary:
        return ""

    text = _TAG_RE.sub(" ", raw_summary)   # pass 1: strip raw tags
    text = html.unescape(text)             # decode entities (&amp;, &#39;, &nbsp;...)
    text = _TAG_RE.sub(" ", text)          # pass 2: catch tags that were entity-escaped
    text = _BOILERPLATE_RE.sub("", text)   # drop trailing "Read more..."/"Also read:" cruft
    text = _WS_RE.sub(" ", text).strip()

    if not text:
        return ""

    title_norm = title.strip().lower()
    text_norm = text.lower()

    if text_norm == title_norm:
        return ""  # summary is just the title again

    if title_norm and text_norm.startswith(title_norm):
        text = text[len(title):].strip(" -:|.")
        if text.lower() == title_norm:
            return ""

    if len(text) < SUMMARY_MIN_LEN:
        return ""  # too short to be a useful summary (e.g. just "- Reuters")

    return text


def _truncate(text, limit=SUMMARY_MAX_LEN):
    if len(text) <= limit:
        return text
    cut = text[:limit]
    last_space = cut.rfind(" ")
    if last_space > limit * 0.6:
        cut = cut[:last_space]
    return cut.rstrip(" ,.;:-") + "…"


def _ai_summary(title, context):
    """Asks Claude for a one-sentence summary. Returns "" on any failure
    (no API key, network error, rate limit, etc.) so callers can fall
    back to the feed's own description - this must never break the
    pipeline just because the AI call didn't work this run."""
    if not _client:
        return ""
    try:
        response = _client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=100,
            system=_AI_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Headline: {title}\n\nExcerpt: {context}" if context else f"Headline: {title}",
            }],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        return text.strip()
    except Exception:
        return ""


def get_summary(entry):
    """Returns a one-sentence summary for an entry, or "" if there's
    nothing useful to show. Shared with web_output.py so the dashboard
    and the WhatsApp alert show the same summary text.

    Prefers an AI-generated summary (set ANTHROPIC_API_KEY to enable);
    falls back to a cleaned version of the feed's own description when
    the API isn't configured or the call fails.
    """
    title = entry.get("title", "").strip()
    cleaned = _clean_summary(entry.get("summary", ""), title)

    ai = _ai_summary(title, cleaned)
    if ai:
        return _truncate(ai)

    return _truncate(cleaned) if cleaned else ""


def format_alert(entry):
    title = entry.get("title", "").strip()
    link = entry.get("link", "").strip()
    source = entry.get("source_feed", "")
    summary = get_summary(entry)

    blocks = [f"📰 *Market Alert*\n{title}"]
    if summary:
        blocks.append(summary)
    blocks.append(f"🔗 {link}\n📡 Source: {source}")

    return "\n\n".join(blocks)
