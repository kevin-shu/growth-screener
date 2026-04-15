import yfinance as yf
import pandas as pd


def fetch_historical(tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Batch download 1 year of daily OHLCV data. Returns (close_df, volume_df)."""
    raw = yf.download(
        tickers,
        period="1y",
        auto_adjust=True,
        threads=True,
        progress=True,
    )
    # With multiple tickers, raw has MultiIndex columns: (field, ticker)
    return raw["Close"], raw["Volume"]
