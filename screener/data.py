import yfinance as yf
import pandas as pd


def fetch_historical(tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Batch download 1 year of daily OHLCV data.
    Falls back to GitHub-hosted price history when Yahoo Finance is unavailable.
    Returns (close_df, volume_df).
    """
    try:
        raw = yf.download(
            tickers,
            period="1y",
            auto_adjust=True,
            threads=True,
            progress=True,
        )
        if not raw.empty and "Close" in raw.columns:
            close = raw["Close"]
            volume = raw["Volume"]
            # Require most tickers to have real data — a handful of lucky
            # successes amid a mostly-failed batch is worse than the
            # GitHub fallback, since it screens a biased sliver of the
            # universe instead of a genuine cross-section.
            coverage = close.notna().any(axis=0).mean()
            if coverage >= 0.5:
                return close, volume
    except Exception:
        pass

    # Fallback: reconstruct from GitHub commit history
    from screener.github_data import fetch_historical_github
    return fetch_historical_github()
