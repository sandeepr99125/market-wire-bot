"""
Formatting layer: turns a raw entry into the text that gets posted.

Keeping this separate means the "how it looks" can change (add
emojis, change layout, add an AI-generated one-line summary instead
of the raw title) without touching fetching, filtering, or posting.
"""


def format_alert(entry):
    title = entry.get("title", "").strip()
    link = entry.get("link", "").strip()
    source = entry.get("source_feed", "")

    # Keep it short and original - a pointer to the story, not a
    # copy of the article itself.
    return f"📰 *Market Alert*\n{title}\n\n🔗 {link}\n📡 Source: {source}"
