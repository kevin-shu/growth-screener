import pandas as pd
import numpy as np


def _rsi(prices: pd.Series, window: int = 14) -> float:
    """Calculate RSI for the latest data point."""
    delta = prices.diff().dropna()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    last_loss = loss.iloc[-1]
    if last_loss == 0:
        return 100.0
    rs = gain.iloc[-1] / last_loss
    return round(100 - (100 / (1 + rs)), 1)


def screen(close: pd.DataFrame, volume: pd.DataFrame) -> pd.DataFrame:
    """
    Screen for surging stocks. Core filters (all must pass):
      1. 5-day cumulative return percentile >= 85% vs own 1-year history
         (captures sustained multi-day strength, not a single-day spike)
      2. Consecutive up days: >= 3 of the last 5 days were positive
         (confirms directional persistence)
      3. Low base: stock was >= 15% below its 6-month high before the surge
         (avoids chasing stocks already at the top)
      4. Price > MA20
         (breakout from base must be confirmed by reclaiming the 20-day average)

    Scoring weights:
      5D percentile 35% + base depth 25% + consecutive days 20% + MA quality 20%
    """
    results = []

    for ticker in close.columns:
        prices = close[ticker].dropna()
        vols   = volume[ticker].dropna()

        # Need at least 145 days: 131 for base window + 11 for base_price look-back + buffer
        # Percentile uses whatever is available (checked separately below)
        if len(prices) < 145 or len(vols) < 21:
            continue

        daily_returns = prices.pct_change().dropna()

        # ── 1. 5-day cumulative return percentile ──────────────────────────
        ret5d_series = prices.pct_change(5).dropna()
        today_ret5d  = float(ret5d_series.iloc[-1])

        # Skip stocks that are flat or down over 5 days
        if today_ret5d <= 0:
            continue

        hist_ret5d = ret5d_series.iloc[-252:-1].dropna()
        if len(hist_ret5d) < 50:
            continue
        pct_rank_5d = float((hist_ret5d < today_ret5d).mean())

        if pct_rank_5d < 0.85:
            continue

        # ── 2. Consecutive up days (last 5 trading days) ───────────────────
        consec_up = int((daily_returns.iloc[-5:] > 0).sum())

        if consec_up < 3:
            continue

        # ── 3. Low base: was stock >= 15% below its 6M high before the surge? ──
        # Use 10 days ago as "before the surge" to be more conservative
        base_price  = float(prices.iloc[-11])
        recent_high = float(prices.iloc[-131:-11].max())
        base_depth  = base_price / recent_high - 1   # negative value
        low_base    = base_depth <= -0.15

        if not low_base:
            continue

        # ── 4. Price must be above MA20 (breakout confirmed) ───────────────
        price_now = float(prices.iloc[-1])
        ma20      = float(prices.iloc[-20:].mean())

        if price_now <= ma20:
            continue

        # ── Supporting metrics ─────────────────────────────────────────────
        ma50          = float(prices.iloc[-50:].mean())
        # MA20 slope: compare current MA20 vs MA20 from 10 trading days ago
        ma20_10d_ago  = float(prices.iloc[-30:-10].mean())
        ma20_rising   = ma20 > ma20_10d_ago

        rsi    = _rsi(prices.iloc[-30:])
        ret1d  = float(daily_returns.iloc[-1])
        ret10d = float(prices.iloc[-1] / prices.iloc[-11] - 1)
        high52w = float(prices.iloc[-252:].max())

        avg_vol = vols.iloc[-21:-1].mean()
        rvol    = float(vols.iloc[-1] / avg_vol) if avg_vol > 0 else 0

        # MA quality score (0–3 flags)
        ma_flags = {
            "ma20_rising":      ma20_rising,           # MA20 itself is trending up
            "above_ma50":       price_now > ma50,      # medium-term trend aligned
            "ma20_above_ma50":  ma20 > ma50,           # golden-cross territory
        }
        ma_score = sum(ma_flags.values()) / 3

        # Composite score (0–1)
        base_score  = min(abs(base_depth) / 0.40, 1.0)   # 40% drawdown = max
        consec_score = consec_up / 5
        score = (pct_rank_5d   * 0.35
                 + base_score  * 0.25
                 + consec_score * 0.20
                 + ma_score    * 0.20)

        results.append({
            "ticker":      ticker,
            "price":       round(price_now, 2),
            "return_1d":   round(ret1d  * 100, 2),
            "return_5d":   round(today_ret5d * 100, 2),
            "return_10d":  round(ret10d * 100, 2),
            "consec_up":   consec_up,            # e.g. 4 means 4 of last 5 days were up
            "base_depth":  round(base_depth * 100, 1),
            "rvol":        round(rvol, 2),
            "rsi":         rsi,
            "pct_rank_5d": round(pct_rank_5d * 100, 1),
            "ma20_rising": ma_flags["ma20_rising"],
            "above_ma50":  ma_flags["above_ma50"],
            "ma_golden":   ma_flags["ma20_above_ma50"],
            "near_52w_high": price_now >= 0.95 * high52w,
            "score":       round(score, 3),
        })

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results).sort_values("score", ascending=False).reset_index(drop=True)
