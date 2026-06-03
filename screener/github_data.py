"""
Fallback data source: reconstruct daily price history from the
Ate329/top-us-stock-tickers GitHub repo, which auto-commits current S&P 500
prices every trading day via GitHub Actions.
"""

import io
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

_BASE = "https://raw.githubusercontent.com/Ate329/top-us-stock-tickers"
_API = "https://api.github.com/repos/Ate329/top-us-stock-tickers/commits"
_FILE = "tickers/sp500.csv"
_FALLBACK_FILE = "tickers/top_200.csv"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; growth-screener/1.0)"}


def _get_commits(max_count: int = 150) -> list[tuple[str, str]]:
    """Fetch recent commit (date, sha) pairs from GitHub API."""
    r = requests.get(_API, params={"per_page": max_count}, headers=_HEADERS, timeout=30)
    r.raise_for_status()
    return [
        (item["commit"]["committer"]["date"][:10], item["sha"])
        for item in r.json()
    ]


def _fetch_one(date_str: str, sha: str) -> tuple[str, dict] | None:
    """Download price CSV for one commit; tries sp500.csv then top_200.csv."""
    for fname in (_FILE, _FALLBACK_FILE):
        url = f"{_BASE}/{sha}/{fname}"
        try:
            r = requests.get(url, headers=_HEADERS, timeout=20)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                prices = df.set_index("symbol")["price"].to_dict()
                return (date_str, prices)
        except Exception:
            continue
    return None


def fetch_historical_github(
    max_workers: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Download price history from Ate329/top-us-stock-tickers GitHub commits.
    Returns (close_df, volume_df) in the same format as fetch_historical().
    """
    commits = _get_commits()
    rows = {}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_one, d, sha): d for d, sha in commits}
        for future in as_completed(futures):
            result = future.result()
            if result:
                date_str, prices = result
                rows[date_str] = prices

    if not rows:
        return pd.DataFrame(), pd.DataFrame()

    close_df = pd.DataFrame(rows).T
    close_df.index = pd.to_datetime(close_df.index)
    close_df = close_df.sort_index()
    close_df = close_df.apply(pd.to_numeric, errors="coerce")
    # De-duplicate: same date may appear in multiple commits, keep last
    close_df = close_df[~close_df.index.duplicated(keep="last")]

    # Volume: synthesise constant value (not available from this source)
    volume_df = pd.DataFrame(1_000_000, index=close_df.index, columns=close_df.columns)

    return close_df, volume_df


def get_current_info() -> pd.DataFrame:
    """Return the latest sp500.csv snapshot for fundamental proxies."""
    commits = _get_commits(max_count=1)
    if not commits:
        return pd.DataFrame(columns=["symbol", "name", "price", "marketCap", "volume", "industry"])
    _, sha = commits[0]
    url = f"{_BASE}/{sha}/{_FILE}"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=20)
        if r.status_code == 200:
            return pd.read_csv(io.StringIO(r.text))
    except Exception:
        pass
    return pd.DataFrame(columns=["symbol", "name", "price", "marketCap", "volume", "industry"])
