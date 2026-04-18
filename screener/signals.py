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


def screen(close: pd.DataFrame, volume: pd.DataFrame,
           require_base_filter: bool = True,
           base_uses_current_price: bool = False,
           weights: tuple = (0.35, 0.25, 0.20, 0.20)) -> pd.DataFrame:
    """
    Screen for surging stocks. Core filters (all must pass):
      1. 5-day cumulative return percentile >= 85% vs own 1-year history
      2. Consecutive up days: >= 3 of the last 5 days were positive
      3. Low base (optional, require_base_filter=True):
         - Old: stock was >= 15% below its 6M high 10 days before screening
         - New: disabled, base_depth used for scoring only
      4. Price > MA20

    base_uses_current_price:
      - False (old): base_depth = price[-11] / price[-131:-11].max() - 1
      - True  (new): base_depth = current_price / 52W_high - 1

    weights: (5D_pct, base, consec, MA) — must sum to 1.0
    """
    w_5d, w_base, w_consec, w_ma = weights
    results = []

    for ticker in close.columns:
        prices = close[ticker].dropna()
        vols   = volume[ticker].dropna()

        if len(prices) < 145 or len(vols) < 21:
            continue

        daily_returns = prices.pct_change().dropna()

        # ── 1. 5-day cumulative return percentile ──────────────────────────
        ret5d_series = prices.pct_change(5).dropna()
        today_ret5d  = float(ret5d_series.iloc[-1])

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

        # ── 3. Base depth ──────────────────────────────────────────────────
        price_now = float(prices.iloc[-1])
        high_52w  = float(prices.iloc[-252:].max())

        if base_uses_current_price:
            # 新邏輯：今日收盤 vs 52 週高點（反映當下距高點的距離）
            base_depth = price_now / high_52w - 1
        else:
            # 舊邏輯：10 天前的股價 vs 前 6 個月高點（排除最近 10 天的急漲）
            base_price  = float(prices.iloc[-11])
            recent_high = float(prices.iloc[-131:-11].max())
            base_depth  = base_price / recent_high - 1

        if require_base_filter and base_depth > -0.15:
            continue

        # ── 4. Price must be above MA20 (breakout confirmed) ───────────────
        ma20 = float(prices.iloc[-20:].mean())

        if price_now <= ma20:
            continue

        # ── Supporting metrics ─────────────────────────────────────────────
        ma50         = float(prices.iloc[-50:].mean())
        ma20_10d_ago = float(prices.iloc[-30:-10].mean())
        ma20_rising  = ma20 > ma20_10d_ago

        rsi    = _rsi(prices.iloc[-30:])
        ret1d  = float(daily_returns.iloc[-1])
        ret10d = float(prices.iloc[-1] / prices.iloc[-11] - 1)

        avg_vol = vols.iloc[-21:-1].mean()
        rvol    = float(vols.iloc[-1] / avg_vol) if avg_vol > 0 else 0

        ma_flags = {
            "ma20_rising":     ma20_rising,
            "above_ma50":      price_now > ma50,
            "ma20_above_ma50": ma20 > ma50,
        }
        ma_score = sum(ma_flags.values()) / 3

        # Composite score (0–1)
        base_score   = min(abs(base_depth) / 0.40, 1.0)
        consec_score = consec_up / 5
        score = (pct_rank_5d  * w_5d
                 + base_score * w_base
                 + consec_score * w_consec
                 + ma_score   * w_ma)

        results.append({
            "ticker":        ticker,
            "price":         round(price_now, 2),
            "return_1d":     round(ret1d * 100, 2),
            "return_5d":     round(today_ret5d * 100, 2),
            "return_10d":    round(ret10d * 100, 2),
            "consec_up":     consec_up,
            "base_depth":    round(base_depth * 100, 1),
            "rvol":          round(rvol, 2),
            "rsi":           rsi,
            "pct_rank_5d":   round(pct_rank_5d * 100, 1),
            "ma20_rising":   ma_flags["ma20_rising"],
            "above_ma50":    ma_flags["above_ma50"],
            "ma_golden":     ma_flags["ma20_above_ma50"],
            "near_52w_high": price_now >= 0.95 * high_52w,
            "score":         round(score, 3),
        })

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results).sort_values("score", ascending=False).reset_index(drop=True)
