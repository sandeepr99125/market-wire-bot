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
    "European Central Bank",
    "ECB",
    "Bank of Japan",
    "BoJ",
]

# Direct macro/monetary/commodity/government-policy terms - matching
# one of these alone is enough (see filters.py). NOT generic terms
# like "stock"/"shares"/"market"/"price", which would match almost
# any single-company stock pick or brokerage note. Organized to match
# the analyst-brief category list this bot is scoped to.
CORE_KEYWORDS = [
    # India market indices - the clearest possible "Indian market" signal
    "sensex", "nifty",
    # Commodities (category: Commodities)
    "gold", "silver", "crude", "oil", "opec",
    "output cut", "production cut",
    # Central bank / rates (category: Rate Decisions, RBI Policy)
    "fed", "federal reserve", "interest rate", "rate hike", "rate cut",
    "rbi", "repo rate", "monetary policy", "mpc",
    # Macro indicators (category: Inflation, Other Macro)
    "inflation", "cpi", "wpi", "gdp", "recession", "pmi",
    "purchasing managers index",
    # Jobs data (category: Jobs Data) - deliberately compound phrases,
    # not bare "jobs"/"employment"/"layoffs", which mostly show up in
    # single-company hiring/firing headlines rather than macro releases
    "unemployment", "payrolls", "non-farm payrolls", "nfp",
    "jobs report", "jobs data", "employment data",
    # Government / fiscal policy (category: Govt Policy)
    "union budget", "gst council", "fiscal deficit", "disinvestment",
    "pli scheme", "production linked incentive", "import duty", "export duty",
    "customs duty", "subsidy", "sebi",
    # Infrastructure / capex (category: Infra/Capex)
    "capex", "capital expenditure", "infrastructure spending",
    "defence budget", "railway budget",
    # FII/DII and mutual fund flows (category: FII-DII Flows, Mutual Fund Flows)
    # "fiis"/"diis"/"fpis" alongside the singular forms - "FIIs pour
    # Rs X crore" is the standard plural phrasing and \bfii\b alone
    # won't match inside "FIIs" (no word boundary before the trailing s)
    "fii", "fiis", "dii", "diis", "fpi", "fpis", "foreign portfolio investors",
    "mutual fund", "amfi", "sip inflows", "fund inflows", "fund outflows",
    # Currency (category: Currency) - "rupee" alone is a strong enough
    # signal on its own; bare "dollar" stays context-only (too generic,
    # matches unrelated "billion dollar deal" single-stock stories)
    "rupee", "dollar index", "dxy", "usd/inr",
    # Credit ratings (category: Other Macro)
    "credit rating", "sovereign rating", "rating upgrade", "rating downgrade",
    "moody's", "s&p global", "fitch ratings",
    # Trade policy (category: Global Policymakers/Tariffs, Govt Policy)
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

# Nifty50 constituents - a single-company story about one of these is
# still a market-wide talking point (they collectively ARE the index),
# so mentioning one exempts a headline from the single-stock-move
# exclusion in filters.py the same way a SECTOR_KEYWORDS hit does. This
# is a snapshot of the index, not a live feed - NSE rebalances Nifty50
# twice a year (March/September), so re-check this list periodically.
NIFTY50_CONSTITUENTS = [
    "Reliance Industries", "TCS", "HDFC Bank", "ICICI Bank", "Infosys",
    "Hindustan Unilever", "ITC", "State Bank of India", "SBI", "Bharti Airtel",
    "Kotak Mahindra Bank", "Larsen & Toubro", "Axis Bank", "Bajaj Finance",
    "Asian Paints", "Maruti Suzuki", "HCL Technologies", "Sun Pharma", "Titan",
    "UltraTech Cement", "Wipro", "Nestle India", "Bajaj Finserv", "ONGC",
    "NTPC", "Power Grid", "JSW Steel", "Tata Motors", "Tata Steel",
    "Adani Enterprises", "Adani Ports", "IndusInd Bank", "Grasim Industries",
    "Tech Mahindra", "Coal India", "Cipla", "Dr Reddy's", "Hindalco",
    "Eicher Motors", "Bajaj Auto", "Britannia", "Divi's Laboratories",
    "Apollo Hospitals", "BPCL", "Hero MotoCorp", "SBI Life", "HDFC Life",
    "Shriram Finance", "LTIMindtree", "Mahindra & Mahindra", "Trent",
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
#   - business-standard.com (all 4 sections - economy/finance/markets/
#     commodities): confirmed Akamai edge-level block (HTTP 403
#     "Access Denied", Server: AkamaiGHost) even with a browser
#     User-Agent - not a header issue, genuinely inaccessible.
#   - zeebiz.com, ndtvprofit.com, reutersagency.com: HTTP 403/301 with
#     no entries (blocked or no public RSS).
RSS_FEEDS = {
    "Economic Times": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "The Hindu BusinessLine": "https://www.thehindubusinessline.com/markets/feeder/default.rss",
    "LiveMint": "https://www.livemint.com/rss/markets",
    "CNBC-TV18": "https://www.cnbctv18.com/commonfeeds/v1/cne/rss/market.xml",
    "BBC Business": "http://feeds.bbci.co.uk/news/business/rss.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "RBI": "https://www.rbi.org.in/pressreleases_rss.xml",
}

# How far back to look on first run (in hours) - avoids flooding you
# with old news the very first time you run the script.
INITIAL_LOOKBACK_HOURS = 6
