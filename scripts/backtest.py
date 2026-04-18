"""
回測腳本：比較舊邏輯（含基期篩選）與新邏輯（純動能，基期僅評分）的表現。

流程：
1. 下載 2 年歷史資料
2. 每隔 SCREEN_FREQ 個交易日同時執行兩套邏輯
3. 衡量 1M / 2M / 3M 三個遠期窗口的報酬
4. 輸出對比表格與報酬分佈
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.rule import Rule

from screener.universe import get_universe
from screener.signals import screen

console = Console()

SCREEN_FREQ     = 5    # 每 5 個交易日執行一次（約每週）
MIN_HISTORY     = 252  # 計算指標所需最少歷史天數
FORWARD_WINDOWS = {"1M": 21, "2M": 42, "3M": 63}
MAX_FORWARD     = max(FORWARD_WINDOWS.values())
TOP_N           = 20

CONFIGS = {
    "舊邏輯": dict(
        require_base_filter=True,
        base_uses_current_price=False,
        weights=(0.35, 0.25, 0.20, 0.20),
    ),
    "新邏輯": dict(
        require_base_filter=False,
        base_uses_current_price=True,
        weights=(0.40, 0.10, 0.25, 0.25),
    ),
    "無基期": dict(
        require_base_filter=False,
        base_uses_current_price=True,
        weights=(0.40, 0.00, 0.30, 0.30),
    ),
}


def _pct(v: float, decimals: int = 1) -> str:
    color = "green" if v >= 0 else "red"
    return f"[{color}]{v*100:+.{decimals}f}%[/{color}]"


def run_backtest():
    console.print(Rule("[bold blue]Backtest — 舊邏輯 vs 新邏輯[/bold blue]"))

    console.print("\nFetching universe...", end=" ")
    tickers = get_universe()
    console.print(f"[green]{len(tickers)} tickers[/green]")

    console.print("Downloading 2 years of data (this takes a while)...")
    raw = yf.download(tickers + ["SPY"], period="2y", auto_adjust=True, progress=True)
    close_all  = raw["Close"]
    volume_all = raw["Volume"]

    trading_dates = close_all.index
    valid_dates   = trading_dates[MIN_HISTORY : -(MAX_FORWARD + 1)]
    screen_dates  = valid_dates[::SCREEN_FREQ]

    console.print(
        f"Screening [cyan]{len(screen_dates)}[/cyan] dates "
        f"({screen_dates[0].date()} → {screen_dates[-1].date()})...\n"
    )

    trades = {name: [] for name in CONFIGS}

    for screen_date in screen_dates:
        idx = trading_dates.get_loc(screen_date)

        close_snap  = close_all.iloc[:idx + 1].drop(columns=["SPY"], errors="ignore")
        volume_snap = volume_all.iloc[:idx + 1].drop(columns=["SPY"], errors="ignore")
        spy_entry   = float(close_all["SPY"].iloc[idx])

        for name, cfg in CONFIGS.items():
            candidates = screen(close_snap, volume_snap, **cfg)
            if candidates.empty:
                continue

            for _, row in candidates.head(TOP_N).iterrows():
                t = row["ticker"]
                if t not in close_all.columns:
                    continue
                entry = float(close_all[t].iloc[idx])
                if pd.isna(entry) or entry == 0:
                    continue

                record = {"date": screen_date.date(), "ticker": t}
                for wname, wdays in FORWARD_WINDOWS.items():
                    fwd_idx = idx + wdays
                    if fwd_idx >= len(close_all):
                        continue
                    exit_   = float(close_all[t].iloc[fwd_idx])
                    spy_exit = float(close_all["SPY"].iloc[fwd_idx])
                    if pd.isna(exit_) or pd.isna(spy_exit):
                        continue
                    fwd = exit_ / entry - 1
                    spy = spy_exit / spy_entry - 1
                    record[f"fwd_{wname}"] = fwd
                    record[f"spy_{wname}"] = spy
                    record[f"exc_{wname}"] = fwd - spy

                if len(record) > 2:  # 至少有一個遠期報酬
                    trades[name].append(record)

    # ── 各時間窗口對比表格 ────────────────────────────────────────
    for wname in FORWARD_WINDOWS:
        console.print(Rule(f"[bold]{wname} 遠期報酬（{FORWARD_WINDOWS[wname]} 個交易日）[/bold]"))

        t = Table(show_lines=True, header_style="bold white on dark_blue")
        t.add_column("指標", min_width=20)
        for name in CONFIGS:
            t.add_column(name, justify="right", min_width=14)

        col_key = f"fwd_{wname}"
        exc_key = f"exc_{wname}"
        stats   = []
        for name in CONFIGS:
            df = pd.DataFrame(trades[name]).dropna(subset=[col_key])
            if df.empty:
                stats.append({})
                continue
            fwd = df[col_key]
            exc = df[exc_key]
            stats.append({
                "n":        len(df),
                "dates":    df["date"].nunique(),
                "win_rate": (fwd > 0).mean(),
                "beat_spy": (exc > 0).mean(),
                "avg_fwd":  fwd.mean(),
                "med_fwd":  fwd.median(),
                "avg_exc":  exc.mean(),
            })

        rows = [
            ("信號總數",          [str(s.get("n", "—"))       for s in stats]),
            ("涵蓋交易日數",      [str(s.get("dates", "—"))   for s in stats]),
            ("勝率（報酬 > 0）",  [_pct(s["win_rate"]) if s else "—" for s in stats]),
            ("打敗大盤比例",      [_pct(s["beat_spy"]) if s else "—" for s in stats]),
            ("平均報酬",          [_pct(s["avg_fwd"])  if s else "—" for s in stats]),
            ("中位數報酬",        [_pct(s["med_fwd"])  if s else "—" for s in stats]),
            ("平均超額報酬",      [_pct(s["avg_exc"])  if s else "—" for s in stats]),
        ]
        for label, vals in rows:
            t.add_row(label, *vals)
        console.print(t)

    # ── 3M 報酬分佈比較 ───────────────────────────────────────────
    console.print(Rule("[bold]3M 報酬分佈比較[/bold]"))

    bins   = [-999, -0.20, -0.10, -0.05, 0, 0.05, 0.10, 0.20, 0.50, 999]
    labels = ["< -20%", "-20~-10%", "-10~-5%", "-5~0%",
              "0~+5%", "+5~+10%", "+10~+20%", "+20~+50%", "> +50%"]

    dist_t = Table(show_lines=True, header_style="bold white on dark_blue")
    dist_t.add_column("區間", min_width=12)
    for name in CONFIGS:
        dist_t.add_column(f"{name}　次數", justify="right", min_width=10)
        dist_t.add_column("佔比",           justify="right", min_width=8)

    dfs = {}
    for name in CONFIGS:
        df = pd.DataFrame(trades[name]).dropna(subset=["fwd_3M"])
        dfs[name] = df

    for label in labels:
        row_vals = [label]
        color = "green" if label.startswith(("0", "+")) else "red"
        for name in CONFIGS:
            df = dfs[name]
            if df.empty:
                row_vals += ["0", "0.0%"]
                continue
            buckets = pd.cut(df["fwd_3M"], bins=bins, labels=labels)
            count = int((buckets == label).sum())
            pct   = count / len(df) * 100
            row_vals += [f"[{color}]{count}[/{color}]", f"[{color}]{pct:.1f}%[/{color}]"]
        dist_t.add_row(*row_vals)

    console.print(dist_t)
    console.print()


if __name__ == "__main__":
    run_backtest()
