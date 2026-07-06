# --- Edit this file to tune what the bot looks for ---

# People whose public statements you want to catch
WATCHLIST_NAMES = [
    "Elon Musk",
    "Donald Trump",
    "Jerome Powell",       # US Fed Chair
    "OPEC",
    "Saudi Arabia oil minister",
]

# Extra keywords - an article mentioning a watchlist name AND one of these
# is considered relevant. This cuts down noise (e.g. Musk tweeting about
# something totally unrelated to markets).
MARKET_KEYWORDS = [
    "oil", "crude", "opec", "stock", "shares", "tariff",
    "interest rate", "fed", "sanctions", "ban", "output cut",
    "production cut", "supply", "market", "price",
]

# Free RSS feeds - no signup, no API key needed.
# Add/remove feeds here as you find better sources for your niche.
RSS_FEEDS = [
    "http://www.moneycontrol.com/rss/latestnews.xml",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.thehindubusinessline.com/markets/feeder/default.rss",
    "https://www.financialexpress.com/market/feed/",
]

# How far back to look on first run (in hours) - avoids flooding you
# with old news the very first time you run the script.
INITIAL_LOOKBACK_HOURS = 6
