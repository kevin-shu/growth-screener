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


def fetch_ticker_info(tickers: list[str]) -> dict[str, dict]:
    """Fetch name, market cap, P/E, and fundamental quality signals per ticker."""
    result = {}
    for t in track(tickers, description="Fetching ticker info..."):
        try:
            info = yf.Ticker(t).info
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
        except Exception:
            result[t] = {
                "name": t, "sector": "", "market_cap": 0,
                "pe_forward": None, "pe_trailing": None,
                "revenue_growth": None, "free_cashflow": None,
                "eps_forward": None, "eps_trailing": None,
                "recommendation": None,
            }
    return result


def get_fundamental_flags(info_dict: dict) -> dict:
    """
    分析基本面健康程度，回傳各項旗標。

    分三種處置：
      remove        → 分析師一致 Strong Sell（市場已放棄），直接移除
      needs_research→ 營收衰退或大額燒錢，但不排除有轉型題材，保留並標 🔍 提示深入研究
      clean         → 無明顯基本面疑慮，正常列出
    """
    rev = info_dict.get("revenue_growth")
    fcf = info_dict.get("free_cashflow")
    rec = info_dict.get("recommendation")

    revenue_declining = rev is not None and rev < -0.05          # 營收年衰退 > 5%
    fcf_burning       = fcf is not None and fcf < -500_000_000   # 年燒錢 > $5億
    analyst_sell      = rec is not None and rec >= 4.5           # Strong Sell 共識

    # 只有 Strong Sell 才真正移除（市場已公開放棄，無轉型共識）
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
        "concerns":        concerns,          # list of human-readable strings
        "concern_str":     "，".join(concerns) if concerns else "",
    }
