import io
import pandas as pd
import requests

# Wikipedia blocks requests without a browser User-Agent
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; growth-screener/1.0)"}


def _read_html(url: str) -> list[pd.DataFrame]:
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return pd.read_html(io.StringIO(resp.text))


def get_universe() -> list[str]:
    """Fetch S&P 500 + NASDAQ-100 tickers from Wikipedia, deduplicated."""
    sp500 = _read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]["Symbol"].tolist()

    ndx100 = []
    try:
        for table in _read_html("https://en.wikipedia.org/wiki/Nasdaq-100"):
            if "Ticker" in table.columns:
                ndx100 = table["Ticker"].tolist()
                break
    except Exception:
        pass

    tickers = list(set(sp500 + ndx100))
    # Yahoo Finance uses '-' instead of '.' in ticker symbols (e.g. BRK.B → BRK-B)
    return [t.replace(".", "-") for t in tickers]
