import yfinance as yf


def fetch_news(ticker: str, max_items: int = 5) -> list[dict]:
    """Fetch recent news headlines for a ticker via Yahoo Finance."""
    try:
        items = yf.Ticker(ticker).news or []
        result = []
        for item in items[:max_items]:
            # yfinance news structure varies by version; handle both formats
            if "content" in item:
                content = item["content"]
                result.append({
                    "title": content.get("title", ""),
                    "source": content.get("provider", {}).get("displayName", ""),
                    "url": content.get("canonicalUrl", {}).get("url", ""),
                })
            else:
                result.append({
                    "title": item.get("title", ""),
                    "source": item.get("source", ""),
                    "url": item.get("link", ""),
                })
        return result
    except Exception:
        return []
