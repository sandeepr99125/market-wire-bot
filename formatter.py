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
import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-haiku-4-5"

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

_AI_SYSTEM_PROMPT = (
    "You write market news analysis for a WhatsApp alert. The message "
    "already shows the article's own preview card above your text (title "
    "plus the source's own excerpt), so don't just restate the raw facts "
    "the reader has already seen. Write 3-4 sentences that briefly touch "
    "what happened, then spend most of the space on the market impact and "
    "the reason behind that impact - the analysis a reader can't already "
    "get from the headline or excerpt. Plain text only - no preamble, no "
    "quotation marks, no restating the headline verbatim, and no section "
    "labels like 'Impact:' or 'Why:' - it should read as one flowing "
    "paragraph, not a template."
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_BOILERPLATE_RE = re.compile(
    r"\b(read more|continue reading|also read|the post .* appeared first on)\b.*",
    re.IGNORECASE,
)

SUMMARY_MAX_LEN = 450
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
            max_tokens=260,
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


def _shorten_link(url):
    """Returns a shortened URL via TinyURL (free, keyless), or the
    original URL unchanged on any failure - a long link is a fine
    fallback, never worth blocking an alert over."""
    if not url:
        return url
    try:
        resp = requests.get(
            "https://tinyurl.com/api-create.php",
            params={"url": url},
            timeout=8,
        )
        resp.raise_for_status()
        short = resp.text.strip()
        return short if short.startswith("http") else url
    except Exception:
        return url


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
    doesn't repeat a "Market Alert" label, the title as its own block,
    or a source line - all of that is redundant with what the card
    already shows. The body is just the analysis text (which itself
    briefly covers what happened, as a fallback if the card doesn't
    render) plus the link.
    """
    link = entry.get("link", "").strip()
    if summary is None:
        summary = get_summary(entry)

    body = summary if summary else entry.get("title", "").strip()

    return f"📰 {body}\n\n{_shorten_link(link)}"
