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

# Free RSS feeds - no signup, no API key needed. Keys are the display
# name shown as the source on WhatsApp/the dashboard (feeds' own
# <title> tags are often long or mangled, so we set our own).
# Add/remove feeds here as you find better sources for your niche.
#
# Feeds deliberately absent because they're dead/blocked, not just
# untried - re-check before re-adding:
#   - financialexpress.com: /feed/ returns HTTP 410 ("Feeds have been
#     disabled"), discontinued RSS site-wide.
#   - moneycontrol.com/rss/latestnews.xml: technically responds, but
#     frozen since April 2024 (no new entries) and was individual
#     stock/brokerage-target calls anyway, not macro news.
#   - business-standard.com, zeebiz.com, ndtvprofit.com,
#     reutersagency.com: all return HTTP 403/301 with no entries
#     (blocked or no public RSS).
RSS_FEEDS = {
    "Economic Times": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "The Hindu BusinessLine": "https://www.thehindubusinessline.com/markets/feeder/default.rss",
    "LiveMint": "https://www.livemint.com/rss/markets",
    "CNBC-TV18": "https://www.cnbctv18.com/commonfeeds/v1/cne/rss/market.xml",
    "BBC Business": "http://feeds.bbci.co.uk/news/business/rss.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
}

# How far back to look on first run (in hours) - avoids flooding you
# with old news the very first time you run the script.
INITIAL_LOOKBACK_HOURS = 6
