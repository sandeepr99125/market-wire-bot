# --- Edit this file to tune what the bot looks for ---

# People whose public statements move broad markets - matching one of
# these alone is enough (see filters.py). Kept to macro/geopolitical
# figures, not company/stock-tied names, so individual stock news
# doesn't sneak in through a name match.
WATCHLIST_NAMES = [
    "Elon Musk",
    "Donald Trump",
    "Narendra Modi",
    "Jerome Powell",       # US Fed Chair
    "RBI Governor",
    "Reserve Bank of India",
    "Nirmala Sitharaman",  # India Finance Minister
    "Xi Jinping",
    "Vladimir Putin",
    "OPEC",
    "Saudi Arabia oil minister",
    "IMF",
    "World Bank",
]

# Macro/sector topics - matching one of these alone is enough (see
# filters.py). Deliberately narrow to broad-market movers (commodities,
# central bank policy, inflation, jobs, geopolitical conflict) and NOT
# generic terms like "stock"/"shares"/"market"/"price", which would
# match almost any single-company stock pick or brokerage note.
MARKET_KEYWORDS = [
    # Commodities
    "gold", "silver", "crude", "oil", "opec",
    "output cut", "production cut",
    # Central bank / rates
    "fed", "federal reserve", "interest rate", "rate hike", "rate cut",
    "rbi", "repo rate", "monetary policy",
    # Macro indicators
    "inflation", "cpi", "wpi", "gdp", "recession",
    "jobs", "employment", "unemployment", "payrolls", "layoffs",
    # Geopolitical conflict with market impact
    "war", "conflict", "ceasefire", "sanctions", "strike", "attack",
    "tension", "iran", "israel", "russia", "ukraine",
    # Trade policy
    "tariff", "trade war",
]

# Free RSS feeds - no signup, no API key needed.
# Add/remove feeds here as you find better sources for your niche.
#
# financialexpress.com is deliberately absent: their /feed/ endpoint
# returns HTTP 410 ("Feeds have been disabled") - they discontinued
# RSS site-wide, not a transient glitch. Every other feed URL pattern
# on their domain just serves the regular HTML page instead of XML.
RSS_FEEDS = [
    "http://www.moneycontrol.com/rss/latestnews.xml",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.thehindubusinessline.com/markets/feeder/default.rss",
]

# How far back to look on first run (in hours) - avoids flooding you
# with old news the very first time you run the script.
INITIAL_LOOKBACK_HOURS = 6
