import io
import pandas as pd
import requests

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; growth-screener/1.0)"}

_SP500_GITHUB = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
_NDX100_GITHUB = "https://raw.githubusercontent.com/datasets/nasdaq-100/main/data/constituents.csv"

_SP500_WIKI   = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_NDX100_WIKI  = "https://en.wikipedia.org/wiki/Nasdaq-100"


def _read_html(url: str) -> list[pd.DataFrame]:
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return pd.read_html(io.StringIO(resp.text))


def _fetch_sp500() -> list[str]:
    try:
        resp = requests.get(_SP500_GITHUB, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        col = next(c for c in df.columns if c.lower() in ("symbol", "ticker"))
        return df[col].tolist()
    except Exception:
        pass
    tables = _read_html(_SP500_WIKI)
    return tables[0]["Symbol"].tolist()


def _fetch_ndx100() -> list[str]:
    try:
        resp = requests.get(_NDX100_GITHUB, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        col = next(c for c in df.columns if c.lower() in ("symbol", "ticker"))
        return df[col].tolist()
    except Exception:
        pass
    try:
        for table in _read_html(_NDX100_WIKI):
            if "Ticker" in table.columns:
                return table["Ticker"].tolist()
    except Exception:
        pass
    return []


def get_universe() -> list[str]:
    """Fetch S&P 500 + NASDAQ-100 tickers, deduplicated."""
    sp500  = _fetch_sp500()
    ndx100 = _fetch_ndx100()
    tickers = list(set(sp500 + ndx100))
    # Yahoo Finance uses '-' instead of '.' in ticker symbols (e.g. BRK.B → BRK-B)
    return [t.replace(".", "-") for t in tickers]
