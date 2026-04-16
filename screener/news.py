import yfinance as yf
from datetime import datetime, timezone


def fetch_news(ticker: str, max_items: int = 5) -> list[dict]:
    """Fetch recent news headlines for a ticker via Yahoo Finance."""
    try:
        items = yf.Ticker(ticker).news or []
        result = []
        for item in items[:max_items]:
            # yfinance news structure varies by version; handle both formats
            if "content" in item:
                content = item["content"]
                # 新格式：pubDate 為 ISO 8601 字串
                pub_date = content.get("pubDate", "")
                date_str = _parse_date(pub_date)
                result.append({
                    "title":  content.get("title", ""),
                    "source": content.get("provider", {}).get("displayName", ""),
                    "url":    content.get("canonicalUrl", {}).get("url", ""),
                    "date":   date_str,
                })
            else:
                # 舊格式：providerPublishTime 為 Unix timestamp
                ts = item.get("providerPublishTime")
                date_str = _parse_date(ts)
                result.append({
                    "title":  item.get("title", ""),
                    "source": item.get("source", ""),
                    "url":    item.get("link", ""),
                    "date":   date_str,
                })
        return result
    except Exception:
        return []


def _parse_date(value) -> str:
    """將 Unix timestamp 或 ISO 8601 字串轉為 MM/DD 格式，解析失敗回傳空字串。"""
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
        elif isinstance(value, str) and value:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            return ""
        return dt.strftime("%-m/%-d")
    except Exception:
        return ""
