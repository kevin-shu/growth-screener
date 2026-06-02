import yfinance as yf
from rich.progress import track


def _rec_label(mean) -> str:
    if mean is None:
        return "—"
    if mean < 1.5: return "Strong Buy"
    if mean < 2.5: return "Buy"
    if mean < 3.5: return "Hold"
    if mean < 4.5: return "Sell"
    return "Strong Sell"


# Industry name mapping from NASDAQ categories to display labels
_INDUSTRY_MAP = {
    "Technology": "Technology",
    "Consumer Discretionary": "Consumer Cyclical",
    "Healthcare": "Healthcare",
    "Financials": "Financial Services",
    "Industrials": "Industrials",
    "Communication Services": "Communication Services",
    "Consumer Staples": "Consumer Defensive",
    "Energy": "Energy",
    "Materials": "Basic Materials",
    "Real Estate": "Real Estate",
    "Utilities": "Utilities",
}


def _github_info_map() -> dict[str, dict]:
    """Build a fallback info dict from the GitHub-hosted S&P 500 snapshot."""
    try:
        from screener.github_data import get_current_info
        df = get_current_info()
        if df.empty:
            return {}
        result = {}
        for _, row in df.iterrows():
            symbol = str(row.get("symbol", "")).strip()
            if not symbol:
                continue
            industry = str(row.get("industry", ""))
            result[symbol] = {
                "name":           str(row.get("name", symbol)),
                "sector":         _INDUSTRY_MAP.get(industry, industry),
                "market_cap":     float(row.get("marketCap", 0) or 0),
                "pe_forward":     None,
                "pe_trailing":    None,
                "revenue_growth": None,
                "free_cashflow":  None,
                "eps_forward":    None,
                "eps_trailing":   None,
                "recommendation": None,
            }
        return result
    except Exception:
        return {}


def fetch_ticker_info(tickers: list[str]) -> dict[str, dict]:
    """Fetch name, market cap, P/E, and fundamental quality signals per ticker."""
    result = {}
    yfinance_ok = False

    for t in track(tickers, description="Fetching ticker info..."):
        try:
            info = yf.Ticker(t).info
            # Check if we actually got data
            if info and info.get("longName") or info.get("shortName"):
                yfinance_ok = True
                result[t] = {
                    "name":           info.get("longName") or info.get("shortName", t),
                    "sector":         info.get("sector", ""),
                    "market_cap":     info.get("marketCap", 0),
                    "pe_forward":     info.get("forwardPE"),
                    "pe_trailing":    info.get("trailingPE"),
                    "revenue_growth": info.get("revenueGrowth"),
                    "free_cashflow":  info.get("freeCashflow"),
                    "eps_forward":    info.get("forwardEps"),
                    "eps_trailing":   info.get("trailingEps"),
                    "recommendation": info.get("recommendationMean"),
                }
            else:
                raise ValueError("empty info")
        except Exception:
            result[t] = {
                "name": t, "sector": "", "market_cap": 0,
                "pe_forward": None, "pe_trailing": None,
                "revenue_growth": None, "free_cashflow": None,
                "eps_forward": None, "eps_trailing": None,
                "recommendation": None,
            }

    # If yfinance returned nothing useful, overlay with GitHub data
    if not yfinance_ok:
        github_map = _github_info_map()
        for t in tickers:
            if t in github_map and (result.get(t, {}).get("name") == t or not result.get(t, {}).get("name")):
                result[t] = github_map[t]

    return result


def get_fundamental_flags(info_dict: dict) -> dict:
    """
    Analyse fundamental health and return flags.

    Three outcomes:
      remove        → analyst consensus Strong Sell
      needs_research→ declining revenue or large cash burn, but no Strong Sell
      clean         → no obvious fundamental concerns
    """
    rev = info_dict.get("revenue_growth")
    fcf = info_dict.get("free_cashflow")
    rec = info_dict.get("recommendation")

    revenue_declining = rev is not None and rev < -0.05
    fcf_burning       = fcf is not None and fcf < -500_000_000
    analyst_sell      = rec is not None and rec >= 4.5

    remove         = analyst_sell
    needs_research = (revenue_declining or fcf_burning) and not analyst_sell

    concerns = []
    if revenue_declining:
        concerns.append(f"營收年減 {abs(rev)*100:.0f}%")
    if fcf_burning:
        concerns.append(f"FCF -{abs(fcf)/1e9:.1f}B")
    if analyst_sell:
        concerns.append(f"分析師評等：{_rec_label(rec)}")

    return {
        "remove":          remove,
        "needs_research":  needs_research,
        "concerns":        concerns,
        "concern_str":     "，".join(concerns) if concerns else "",
    }
