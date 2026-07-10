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
    "You write market news analysis for a WhatsApp alert. The message "
    "already shows the article's own preview card above your text (title "
    "plus the source's own excerpt), so don't just restate the raw facts "
    "the reader has already seen.\n\n"
    "Respond using EXACTLY this line format:\n"
    "WHAT: <one brief sentence on what happened>\n"
    "IMPACT: <one sentence on the market impact>\n"
    "REASON: <one sentence on why this has that impact>\n\n"
    "Always include the WHAT line. Only include the IMPACT line if there's "
    "a real market impact worth noting, and only include the REASON line "
    "if the reason isn't already obvious from WHAT/IMPACT - omit either "
    "line entirely rather than padding it with generic filler just to "
    "fill out the format. Each line is plain text - no quotation marks, "
    "no restating the headline verbatim."
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_BOILERPLATE_RE = re.compile(
    r"\b(read more|continue reading|also read|the post .* appeared first on)\b.*",
    re.IGNORECASE,
)

SUMMARY_MAX_LEN = 550
SUMMARY_MIN_LEN = 15

_REQUIRED_STRUCTURED_LABEL = "Market Alert"

# (prefix Claude uses, display label, icon shown before the label - the
# leading 📰 in format_alert() already marks "Market Alert" itself, so
# it has no separate icon here).
_STRUCTURED_LINE_PREFIXES = (
    ("WHAT:", _REQUIRED_STRUCTURED_LABEL, None),
    ("IMPACT:", "Impact", "💥"),
    ("REASON:", "Reason", "💡"),
)


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


def _parse_structured_summary(text):
    """Parses the WHAT:/IMPACT:/REASON: lines Claude was asked to
    produce into a labeled, WhatsApp-formatted block (bold labels with
    a small icon, blank line between each). Only the WHAT/"Market
    Alert" line is required - IMPACT and REASON are included only when
    Claude actually wrote them, since not every story has a meaningful
    impact or a non-obvious reason worth a dedicated line. Returns ""
    if even the required line is missing - relying on freeform
    formatting to always come out right isn't safe, so a response that
    doesn't match the expected shape falls back to the feed's own
    description instead."""
    parts = {}
    for line in text.strip().splitlines():
        line = line.strip()
        for prefix, label, _icon in _STRUCTURED_LINE_PREFIXES:
            if line.upper().startswith(prefix):
                value = line[len(prefix):].strip()
                if value:
                    parts[label] = value

    if _REQUIRED_STRUCTURED_LABEL not in parts:
        return ""

    blocks = []
    for _prefix, label, icon in _STRUCTURED_LINE_PREFIXES:
        if label in parts:
            icon_str = f"{icon} " if icon else ""
            blocks.append(f"{icon_str}*{label}:* {parts[label]}")

    return "\n\n".join(blocks)


def _ai_summary(title, context):
    """Asks Claude for a what/impact/reason breakdown. Returns "" on
    any failure (no API key, network error, rate limit, response that
    doesn't match the expected format, etc.) so callers can fall back
    to the feed's own description - this must never break the
    pipeline just because the AI call didn't work this run."""
    if not _client:
        return ""
    try:
        response = _client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=260,
            system=_AI_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Headline: {title}\n\nExcerpt: {context}" if context else f"Headline: {title}",
            }],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        return _parse_structured_summary(text)
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


def format_alert(entry, summary=None):
    """summary can be precomputed (e.g. fetched concurrently for a
    batch of entries) to avoid a redundant get_summary() call - pass
    None to have it computed here.

    WhatsApp auto-generates a rich preview card (image, title, the
    source's own excerpt, domain) from the link, so the message body
    doesn't repeat the title as its own block or a source line -
    that's redundant with what the card already shows. The body is
    just the analysis text (which falls back to the raw title if
    there's no summary) plus the bare link - WhatsApp can only build
    a tappable preview card from a URL that's literally present as
    text, so the link can't be hidden, but it's shown plainly with no
    extra decoration around it. Uses the direct article URL, not a
    shortener, so tapping the card or the link goes straight there
    with no extra redirect hop.
    """
    link = entry.get("link", "").strip()
    if summary is None:
        summary = get_summary(entry)

    body = summary if summary else entry.get("title", "").strip()

    return f"📰 {body}\n\n{link}"
