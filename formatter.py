"""
Formatting layer: turns a raw entry into the text that gets posted.

Keeping this separate means the "how it looks" can change (add
emojis, change layout, add an AI-generated one-line summary instead
of the raw title) without touching fetching, filtering, or posting.
"""

import html
import re

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


def format_alert(entry):
    title = entry.get("title", "").strip()
    link = entry.get("link", "").strip()
    source = entry.get("source_feed", "")
    summary = _clean_summary(entry.get("summary", ""), title)

    blocks = [f"📰 *Market Alert*\n{title}"]
    if summary:
        blocks.append(_truncate(summary))
    blocks.append(f"🔗 {link}\n📡 Source: {source}")

    return "\n\n".join(blocks)
