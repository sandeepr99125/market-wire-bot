"""
Market KPI layer: fetches a handful of headline numbers (indices,
commodities, FX, institutional flows) for the dashboard strip.

Every source here is free and keyless, same spirit as the RSS feeds -
but unofficial/undocumented endpoints like these can fail or get
rate-limited at any time (NSE's FII/DII endpoint in particular is
known to block cloud/datacenter IPs, which is exactly what GitHub
Actions runners are). Each fetch is wrapped so one failure doesn't
blank out the whole strip: on failure we keep whatever value was
last successfully fetched, rather than showing nothing.
"""

import json
import os
from datetime import datetime, timezone

import requests

KPI_FILE = os.path.join(os.path.dirname(__file__), "market_kpis.json")

_YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}
_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
}

TROY_OZ_TO_GRAMS = 31.1034768

# NSE sector indices, all confirmed live on Yahoo Finance's unofficial
# endpoint (same source as the other indices here) - one ticker
# (^CNXFINANCE, "Nifty Financial Services") was tried and dropped:
# Yahoo returns "No data found, symbol may be delisted" for it.
SECTOR_INDICES = {
    "sector_bank": ("Bank", "%5ENSEBANK"),
    "sector_it": ("IT", "%5ECNXIT"),
    "sector_metal": ("Metal", "%5ECNXMETAL"),
    "sector_auto": ("Auto", "%5ECNXAUTO"),
    "sector_pharma": ("Pharma", "%5ECNXPHARMA"),
    "sector_fmcg": ("FMCG", "%5ECNXFMCG"),
    "sector_energy": ("Energy", "%5ECNXENERGY"),
    "sector_realty": ("Realty", "%5ECNXREALTY"),
    "sector_psu_bank": ("PSU Bank", "%5ECNXPSUBANK"),
}


def _fetch_yahoo_quote(ticker):
    """Returns (price, change_pct) for a Yahoo Finance ticker, or None
    on any failure (network error, rate limit, unexpected shape)."""
    try:
        resp = requests.get(
            _YAHOO_URL.format(ticker=ticker),
            headers=_YAHOO_HEADERS,
            params={"range": "1d", "interval": "1m"},
            timeout=10,
        )
        resp.raise_for_status()
        meta = resp.json()["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else None
        return price, change_pct
    except Exception:
        return None


def _fetch_usd_inr():
    """Returns the USD/INR rate, or None on failure."""
    try:
        resp = requests.get(
            "https://api.frankfurter.dev/v1/latest",
            params={"from": "USD", "to": "INR"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["rates"]["INR"]
    except Exception:
        return None


def _fetch_fii_dii():
    """Returns {"fii": {...}, "dii": {...}} (only the keys that
    succeeded), or {} on total failure. NSE's endpoint is known to
    block cloud/datacenter IPs, so failure here is expected sometimes."""
    try:
        session = requests.Session()
        session.headers.update(_NSE_HEADERS)
        session.get("https://www.nseindia.com/", timeout=10)  # warm up session cookies
        resp = session.get("https://www.nseindia.com/api/fiidiiTradeReact", timeout=10)
        resp.raise_for_status()
        rows = resp.json()

        result = {}
        for row in rows:
            key = "fii" if "FII" in row.get("category", "") else "dii"
            result[key] = {
                "net_value_cr": float(row["netValue"]),
                "date": row["date"],
            }
        return result
    except Exception:
        return {}


def load_kpis():
    """Returns whatever's currently in market_kpis.json - used both to
    merge over on the next fetch, and by digest.py to pull the latest
    sector snapshot into the digest prompt."""
    if os.path.exists(KPI_FILE):
        try:
            with open(KPI_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def fetch_market_kpis():
    """Fetches all KPIs and writes them to market_kpis.json, merging
    over whatever was there before - a failed fetch this run keeps
    the previous value (with its own fetched_at) instead of going
    blank. Returns the merged dict."""
    kpis = load_kpis()
    now = datetime.now(timezone.utc).isoformat()

    def _set(key, fields):
        kpis[key] = {**fields, "fetched_at": now}

    nifty = _fetch_yahoo_quote("%5ENSEI")
    if nifty:
        _set("nifty", {"label": "NIFTY 50", "value": round(nifty[0], 2), "change_pct": _round_or_none(nifty[1])})

    sensex = _fetch_yahoo_quote("%5EBSESN")
    if sensex:
        _set("sensex", {"label": "SENSEX", "value": round(sensex[0], 2), "change_pct": _round_or_none(sensex[1])})

    gold = _fetch_yahoo_quote("GC=F")
    if gold:
        _set("gold", {"label": "Gold (Spot)", "value": round(gold[0], 2), "change_pct": _round_or_none(gold[1]), "unit": "$/oz"})

    silver = _fetch_yahoo_quote("SI=F")
    if silver:
        _set("silver", {"label": "Silver (Spot)", "value": round(silver[0], 2), "change_pct": _round_or_none(silver[1]), "unit": "$/oz"})

    crude = _fetch_yahoo_quote("BZ=F")
    if crude:
        _set("crude", {"label": "Crude (Brent)", "value": round(crude[0], 2), "change_pct": _round_or_none(crude[1]), "unit": "$/bbl"})

    usd_inr = _fetch_usd_inr()
    if usd_inr is not None:
        _set("usd_inr", {"label": "USD/INR", "value": round(usd_inr, 2)})

    # Approximate India retail rate, derived from the global spot price
    # + USD/INR fetched just now - only computed when both are fresh
    # in this same run, so we never mix prices from different times.
    # This will NOT match actual MCX/bullion rates exactly (import
    # duty, GST, and dealer premium aren't reflected), hence "approx"
    # in the label - it's a directional figure, not the local price.
    if gold and usd_inr is not None:
        gold_inr_per_10g = (gold[0] / TROY_OZ_TO_GRAMS) * 10 * usd_inr
        _set("gold_inr_approx", {"label": "Gold ₹/10g (approx)", "value": round(gold_inr_per_10g)})

    if silver and usd_inr is not None:
        silver_inr_per_kg = (silver[0] / TROY_OZ_TO_GRAMS) * 1000 * usd_inr
        _set("silver_inr_approx", {"label": "Silver ₹/kg (approx)", "value": round(silver_inr_per_kg)})

    fii_dii = _fetch_fii_dii()
    for key in ("fii", "dii"):
        if key in fii_dii:
            _set(key, {"label": key.upper(), **fii_dii[key]})

    for key, (label, ticker) in SECTOR_INDICES.items():
        quote = _fetch_yahoo_quote(ticker)
        if quote:
            _set(key, {"label": f"Nifty {label}", "value": round(quote[0], 2), "change_pct": _round_or_none(quote[1])})

    with open(KPI_FILE, "w") as f:
        json.dump(kpis, f, indent=2)

    return kpis


def _round_or_none(value):
    return round(value, 2) if value is not None else None
