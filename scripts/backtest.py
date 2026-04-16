"""
回測腳本：驗證 screener 選出的股票在 3 個月後（~63 個交易日）的表現。

流程：
1. 下載 2 年歷史資料（需要足夠的歷史來計算指標 + 足夠的未來資料來衡量報酬）
2. 每隔 SCREEN_FREQ 個交易日模擬執行一次 screener（only use data up to that date）
3. 記錄每個信號的 3 個月後報酬，並與 SPY 比較
"""

import sys
from pathlib import Path
# 將專案根目錄加入 sys.path，使 screener/ 模組可被找到
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.rule import Rule

from screener.universe import get_universe
from screener.signals import screen

console = Console()

FORWARD_DAYS = 63   # ~3 個月
SCREEN_FREQ  = 5    # 每 5 個交易日執行一次 screener（約每週）
MIN_HISTORY  = 252  # 計算指標所需最少交易日數


def _pct(v: float, decimals: int = 1) -> str:
    color = "green" if v > 0 else "red"
    return f"[{color}]{v*100:+.{decimals}f}%[/{color}]"


def run_backtest():
    console.print(Rule("[bold blue]Backtest — 3 個月後表現驗證[/bold blue]"))

    # 1. 取得股票清單
    console.print("\nFetching universe...", end=" ")
    tickers = get_universe()
    console.print(f"[green]{len(tickers)} tickers[/green]")

    # 2. 下載 2 年 OHLCV（包含 SPY 作為 benchmark）
    console.print("Downloading 2 years of data (this takes a while)...")
    all_tickers = tickers + ["SPY"]
    raw = yf.download(all_tickers, period="2y", auto_adjust=True, progress=True)
    close_all  = raw["Close"]
    volume_all = raw["Volume"]

    trading_dates = close_all.index

    # 有效的 screening 日期範圍：
    #   - 前面至少要有 MIN_HISTORY 天才能計算指標
    #   - 後面至少要有 FORWARD_DAYS 天才能量測報酬
    valid_dates    = trading_dates[MIN_HISTORY : -(FORWARD_DAYS + 1)]
    screen_dates   = valid_dates[::SCREEN_FREQ]  # 每隔 SCREEN_FREQ 天取一次

    console.print(f"Screening [cyan]{len(screen_dates)}[/cyan] dates "
                  f"({screen_dates[0].date()} → {screen_dates[-1].date()})...\n")

    trades = []

    for screen_date in screen_dates:
        idx = trading_dates.get_loc(screen_date)

        # 只用 screen_date 當天及之前的資料（避免 look-ahead bias）
        close_snap  = close_all.iloc[: idx + 1].drop(columns=["SPY"], errors="ignore")
        volume_snap = volume_all.iloc[: idx + 1].drop(columns=["SPY"], errors="ignore")

        candidates = screen(close_snap, volume_snap)
        if candidates.empty:
            continue

        # 3 個月後的報酬
        fwd_idx   = idx + FORWARD_DAYS
        spy_entry = close_all["SPY"].iloc[idx]
        spy_exit  = close_all["SPY"].iloc[fwd_idx]
        spy_ret   = spy_exit / spy_entry - 1

        for _, row in candidates.iterrows():
            t = row["ticker"]
            if t not in close_all.columns:
                continue
            entry = close_all[t].iloc[idx]
            exit_ = close_all[t].iloc[fwd_idx]
            if pd.isna(entry) or pd.isna(exit_) or entry == 0:
                continue

            fwd_ret = exit_ / entry - 1
            trades.append({
                "date":          screen_date.date(),
                "ticker":        t,
                "signal_ret1d":  row["return_1d"],
                "signal_rvol":   row["rvol"],
                "signal_score":  row["score"],
                "fwd_ret":       fwd_ret,
                "spy_ret":       spy_ret,
                "excess_ret":    fwd_ret - spy_ret,
            })

    if not trades:
        console.print("[yellow]回測期間沒有找到任何符合條件的信號。[/yellow]")
        return

    df = pd.DataFrame(trades)
    n  = len(df)
    n_dates = df["date"].nunique()

    # ── 整體統計 ──────────────────────────────────────────────────
    console.print(Rule("[bold]整體統計[/bold]"))
    console.print(f"  回測期間信號總數：[cyan]{n}[/cyan] 個（來自 {n_dates} 個交易日）\n")

    stats = [
        ("勝率（3M 後上漲）",          (df["fwd_ret"] > 0).mean()),
        ("打敗大盤的比例",              (df["excess_ret"] > 0).mean()),
        ("平均 3M 報酬",               df["fwd_ret"].mean()),
        ("中位數 3M 報酬",             df["fwd_ret"].median()),
        ("同期 SPY 平均報酬",          df["spy_ret"].mean()),
        ("平均超額報酬（alpha）",       df["excess_ret"].mean()),
    ]

    st = Table(show_header=False, box=None, padding=(0, 3))
    st.add_column("指標", style="dim", min_width=22)
    st.add_column("數值", style="bold")
    for label, val in stats:
        if isinstance(val, float) and abs(val) < 10:  # ratio → percentage
            st.add_row(label, _pct(val))
        else:
            st.add_row(label, str(val))
    console.print(st)

    # ── 報酬分佈長條圖 ────────────────────────────────────────────
    console.print(Rule("[bold]3M 報酬分佈[/bold]"))
    bins   = [-999, -0.20, -0.10, -0.05, 0, 0.05, 0.10, 0.20, 0.50, 999]
    labels = ["< -20%", "-20~-10%", "-10~-5%", "-5~0%",
              "0~+5%", "+5~+10%", "+10~+20%", "+20~+50%", "> +50%"]
    df["bucket"] = pd.cut(df["fwd_ret"], bins=bins, labels=labels)
    dist = df["bucket"].value_counts().reindex(labels, fill_value=0)

    for label, count in dist.items():
        pct   = count / n * 100
        bar   = "█" * max(1, int(pct / 1.5)) if count else ""
        color = "green" if label.startswith(("0", "+")) else "red"
        console.print(f"  [{color}]{label:>12}[/{color}]  {bar} {count} ({pct:.1f}%)")

    # ── 多次出現的個股表現 ────────────────────────────────────────
    console.print(Rule("[bold]多次出現的個股（≥ 2 次信號）[/bold]"))
    ticker_stats = (
        df.groupby("ticker")
        .agg(
            signals   = ("fwd_ret", "count"),
            avg_fwd   = ("fwd_ret", "mean"),
            avg_excess= ("excess_ret", "mean"),
            win_rate  = ("fwd_ret", lambda x: (x > 0).mean()),
        )
        .query("signals >= 2")
        .sort_values("avg_fwd", ascending=False)
    )

    tt = Table(show_lines=True, header_style="bold white on dark_blue")
    tt.add_column("Ticker",          style="bold cyan", width=8)
    tt.add_column("信號次數",        justify="right", width=8)
    tt.add_column("平均 3M 報酬",    justify="right", width=14)
    tt.add_column("平均超額報酬",    justify="right", width=14)
    tt.add_column("勝率",            justify="right", width=8)

    for t, row in ticker_stats.head(20).iterrows():
        tt.add_row(
            t,
            str(int(row["signals"])),
            _pct(row["avg_fwd"]),
            _pct(row["avg_excess"]),
            f"{row['win_rate']*100:.0f}%",
        )
    console.print(tt)

    # ── 最差的個股（避開地雷）────────────────────────────────────
    console.print(Rule("[bold]表現最差的個股（≥ 2 次信號）[/bold]"))
    worst = ticker_stats.sort_values("avg_fwd").head(10)
    wt = Table(show_lines=True, header_style="bold white on dark_red")
    wt.add_column("Ticker",          style="bold red", width=8)
    wt.add_column("信號次數",        justify="right", width=8)
    wt.add_column("平均 3M 報酬",    justify="right", width=14)
    wt.add_column("平均超額報酬",    justify="right", width=14)
    wt.add_column("勝率",            justify="right", width=8)
    for t, row in worst.iterrows():
        wt.add_row(
            t,
            str(int(row["signals"])),
            _pct(row["avg_fwd"]),
            _pct(row["avg_excess"]),
            f"{row['win_rate']*100:.0f}%",
        )
    console.print(wt)

    console.print()


if __name__ == "__main__":
    run_backtest()
