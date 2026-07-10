# --- Edit this file to tune what the bot looks for ---

# People who move markets when they speak - but they also generate a
# lot of purely personal/political news with zero market relevance
# (Trump's son's crypto bets, Musk's other companies). So a name hit
# alone is NOT enough for this group (see filters.py) - it must be
# paired with an economic-context word from ECONOMIC_CONTEXT_KEYWORDS
# below, or one of the other keyword lists.
WATCHLIST_PEOPLE = [
    "Elon Musk",
    "Donald Trump",
    "Narendra Modi",
    "Jerome Powell",       # US Fed Chair
    "RBI Governor",
    "Nirmala Sitharaman",  # India Finance Minister
    "Xi Jinping",
    "Vladimir Putin",
]

# Institutions whose statements are inherently economic news - unlike
# WATCHLIST_PEOPLE, a mention alone is enough, no context word needed.
WATCHLIST_INSTITUTIONS = [
    "Reserve Bank of India",
    "OPEC",
    "Saudi Arabia oil minister",
    "IMF",
    "World Bank",
]

# Direct macro/monetary/commodity/government-policy terms - matching
# one of these alone is enough (see filters.py). NOT generic terms
# like "stock"/"shares"/"market"/"price", which would match almost
# any single-company stock pick or brokerage note.
CORE_KEYWORDS = [
    # India market indices - the clearest possible "Indian market" signal
    "sensex", "nifty",
    # Commodities
    "gold", "silver", "crude", "oil", "opec",
    "output cut", "production cut",
    # Central bank / rates
    "fed", "federal reserve", "interest rate", "rate hike", "rate cut",
    "rbi", "repo rate", "monetary policy", "mpc",
    # Macro indicators
    "inflation", "cpi", "wpi", "gdp", "recession",
    "jobs", "employment", "unemployment", "payrolls", "layoffs",
    # Government / fiscal policy - "government changes which impact market"
    "union budget", "gst council", "fiscal deficit", "disinvestment",
    # Trade policy
    "tariff", "trade war",
]

# Sector-wide language ONLY - deliberately compound phrases like "bank
# nifty"/"metal stocks", not bare words like "bank"/"metal"/"electric",
# which would also match single-company stock stories ("XYZ Bank
# shares rally 5%"). See filters.py: matching one of these alone also
# skips the single-stock exclusion check, since these phrases already
# signal sector-wide (not one company's) framing.
SECTOR_KEYWORDS = [
    "banking sector", "bank nifty", "psu bank", "private banks", "nbfc sector",
    "metal stocks", "metal sector", "steel sector", "aluminium prices", "copper prices", "base metals",
    "electric vehicle", "ev sales", "ev policy", "ev subsidy",
]

# Geopolitical conflict terms - deliberately NOT sufficient alone (see
# filters.py). Global feeds (BBC, Al Jazeera) carry a constant stream
# of war/conflict reporting with no bearing on Indian markets; a hit
# here only counts when paired with an economic-context word, so
# "Israel strikes Iran, oil surges" passes but plain war/casualty
# reporting doesn't.
GEOPOLITICAL_KEYWORDS = [
    "war", "conflict", "ceasefire", "sanctions", "strike", "attack",
    "tension", "iran", "israel", "russia", "ukraine",
]

# Companion words - what makes a WATCHLIST_PEOPLE or GEOPOLITICAL_KEYWORDS
# hit actually market-relevant (see filters.py). Deliberately excludes
# generic terms like "investors"/"investment" - those are common in
# purely personal financial-advice pieces ("retail investors losing
# money in Tesla crash") that have nothing to do with Indian markets.
ECONOMIC_CONTEXT_KEYWORDS = [
    "market", "markets", "economy", "economic", "growth", "trade",
    "rupee", "dollar", "stocks", "sensex", "nifty", "export", "exports",
    "import", "imports", "supply", "shipping", "prices", "price",
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
