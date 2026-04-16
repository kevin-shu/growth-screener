import sys
from pathlib import Path
# 將專案根目錄加入 sys.path，使 screener/ 模組可被找到
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from datetime import date

from rich.console import Console
from rich.table import Table
from rich.rule import Rule
from deep_translator import GoogleTranslator

from screener.universe import get_universe
from screener.data import fetch_historical
from screener.signals import screen
from screener.info import fetch_ticker_info, get_fundamental_flags
from screener.news import fetch_news

console = Console()

TOP_N          = 20   # 技術篩選後取前 N 支
NEWS_TOP_N     = 5    # 一般新聞顯示前 N 支
REPORTS_DIR    = Path(__file__).parent.parent / "daily-reports"


def _translate_news(items: list[dict]) -> list[dict]:
    """將新聞標題批次翻譯為繁體中文（保留 source 與 url）。"""
    if not items:
        return items
    titles = [item.get("title", "") for item in items]
    try:
        translated = GoogleTranslator(source="en", target="zh-TW").translate_batch(titles)
        return [{**item, "title": t or item["title"]} for item, t in zip(items, translated)]
    except Exception:
        return items  # 翻譯失敗時回傳原標題


# ── Terminal formatters ────────────────────────────────────────────────────

def _fmt_cap(cap: float) -> str:
    if cap >= 1e12: return f"${cap/1e12:.1f}T"
    if cap >= 1e9:  return f"${cap/1e9:.1f}B"
    return f"${cap/1e6:.0f}M" if cap else "—"

def _fmt_pe(pe) -> str:
    return f"{pe:.1f}x" if pe and pe > 0 else "—"

def _fmt_rev(v) -> str:
    if v is None: return "[dim]—[/dim]"
    pct = v * 100
    if pct >= 10:  return f"[green]+{pct:.0f}%[/green]"
    if pct >= 0:   return f"[yellow]+{pct:.0f}%[/yellow]"
    return f"[red]{pct:.0f}%[/red]"

def _fmt_fcf(fcf) -> str:
    if fcf is None: return "[dim]—[/dim]"
    return f"[green]+${fcf/1e9:.1f}B[/green]" if fcf >= 0 else f"[red]-${abs(fcf)/1e9:.1f}B[/red]"

def _fmt_rec(rec) -> str:
    if rec is None: return "[dim]—[/dim]"
    if rec < 1.5:  return "[bold green]Strong Buy[/bold green]"
    if rec < 2.5:  return "[green]Buy[/green]"
    if rec < 3.5:  return "[yellow]Hold[/yellow]"
    if rec < 4.5:  return "[red]Sell[/red]"
    return "[bold red]Strong Sell[/bold red]"


# ── Markdown report (Chinese) ─────────────────────────────────────────────

def _rec_label_zh(rec) -> str:
    if rec is None: return "—"
    if rec < 1.5:  return "強力買入"
    if rec < 2.5:  return "買入"
    if rec < 3.5:  return "持有"
    if rec < 4.5:  return "賣出"
    return "強力賣出"

def _rev_zh(v) -> str:
    if v is None: return "—"
    return f"{v*100:+.0f}%"

def _fcf_zh(fcf) -> str:
    if fcf is None: return "—"
    s = f"+${fcf/1e9:.1f}B" if fcf >= 0 else f"-${abs(fcf)/1e9:.1f}B"
    return s

def _ma_zh(row) -> str:
    parts = []
    if row.ma20_rising: parts.append("MA20上升")
    if row.above_ma50:  parts.append("站上MA50")
    if row.ma_golden:   parts.append("黃金排列")
    return "、".join(parts) if parts else "均線偏弱"


def _update_index():
    """掃描 daily-reports/ 資料夾，重新產生 index.json（日期由新到舊）。"""
    import json
    dates = sorted(
        [p.stem for p in REPORTS_DIR.glob("????-??-??.md")],
        reverse=True,
    )
    (REPORTS_DIR / "index.json").write_text(json.dumps(dates, ensure_ascii=False), encoding="utf-8")


def _write_daily_report(today: date, final: pd.DataFrame, info: dict,
                        flags_map: dict, removed: list, news_map: dict):
    """將今日篩選結果以中文寫入 daily-reports/YYYY-MM-DD.md，並更新 index.json。"""

    lines = []
    lines.append(f"## {today.strftime('%Y-%m-%d')}\n")
    lines.append(f"> 資料日期：{today.strftime('%Y/%m/%d')}  |  篩選宇宙：S&P 500 + NASDAQ-100\n")

    # ── 篩選結果表格 ──────────────────────────────────────────────────────
    lines.append(f"### 篩選結果（共 {len(final)} 支）\n")
    lines.append(
        "| # | 代號 | 公司名稱 | 產業 | 股價 | 日漲 | 5日漲 | 10日漲 "
        "| 連漲/5 | 基期 | 均線狀態 | RSI | 評分 "
        "| 營收成長 | 自由現金流 | 分析師 | 預估本益比 | 市值 |"
    )
    lines.append(
        "|---|------|----------|------|------|------|-------|------"
        "|--------|------|----------|-----|------"
        "|----------|-----------|--------|------------|------|"
    )

    for i, row in enumerate(final.itertuples(), 1):
        t   = row.ticker
        inf = info.get(t, {})
        flg = flags_map.get(t, {})
        name   = inf.get("name") or t
        sector = inf.get("sector") or "—"

        badges = ("★" if row.near_52w_high else "") + (" 🔍" if flg.get("needs_research") else "")
        ticker_cell = f"**{t}**" + (f" {badges.strip()}" if badges.strip() else "")

        eps_fwd = inf.get("eps_forward")
        eps_ttm = inf.get("eps_trailing")
        eps_arrow = (" ↑" if eps_fwd and eps_ttm and eps_fwd > eps_ttm
                     else " ↓" if eps_fwd and eps_ttm and eps_fwd < eps_ttm
                     else "")

        lines.append(
            f"| {i} | {ticker_cell} | {name} | {sector} "
            f"| ${row.price:,.2f} "
            f"| {row.return_1d:+.1f}% | {row.return_5d:+.1f}% | {row.return_10d:+.1f}% "
            f"| {row.consec_up}/5 | {row.base_depth:.1f}% "
            f"| {_ma_zh(row)} | {row.rsi} | {row.score:.3f} "
            f"| {_rev_zh(inf.get('revenue_growth'))} "
            f"| {_fcf_zh(inf.get('free_cashflow'))}{eps_arrow} "
            f"| {_rec_label_zh(inf.get('recommendation'))} "
            f"| {_fmt_pe(inf.get('pe_forward'))} | {_fmt_cap(inf.get('market_cap', 0))} |"
        )

    lines.append("")

    # ── 需深入研究 ────────────────────────────────────────────────────────
    research_tickers = [t for t, flg in flags_map.items() if flg.get("needs_research")]
    if research_tickers:
        lines.append("### 🔍 需深入研究（基本面疑慮，但技術面已突破）\n")
        lines.append(
            "以下股票基本面目前偏弱（營收衰退或大額燒錢），"
            "但技術面已展現強勢突破，背後可能存在尚未在財報反映的轉型題材。"
            "建議對照以下新聞，自行判斷是否有可信的反轉故事。\n"
        )
        for t in research_tickers:
            inf = info.get(t, {})
            flg = flags_map.get(t, {})
            name = inf.get("name", t)
            concerns = "、".join(flg.get("concerns", []))
            lines.append(f"#### {t}　{name}")
            lines.append(f"- **基本面狀況**：{concerns}")
            lines.append(f"- **技術面**：近期漲幅異常強勢，已突破 MA20" +
                         ("，接近 52 週高點（★）" if any(
                             r.ticker == t and r.near_52w_high for r in final.itertuples()
                         ) else ""))

            news_items = _translate_news(news_map.get(t, []))
            if news_items:
                lines.append("- **相關新聞（供參考是否有轉型佐證）**：")
                for item in news_items:
                    title  = item.get("title", "")
                    source = item.get("source", "")
                    url    = item.get("url", "")
                    if title:
                        src_link = f"[{source}]({url})" if url else source
                        date_prefix = f"({item.get('date')}) " if item.get("date") else ""
                        lines.append(f"  - {date_prefix}{title} *— {src_link}*")
            else:
                lines.append("- **相關新聞**：目前未找到明顯催化劑，可自行搜尋公司近期法說或產品動態")
            lines.append("")

    # ── 已移除 ────────────────────────────────────────────────────────────
    if removed:
        lines.append("### ✗ 已移除（分析師共識為強力賣出）\n")
        for t, concern_str in removed:
            name = info.get(t, {}).get("name", t)
            lines.append(f"- **{t}** {name}　— {concern_str}")
        lines.append("")

    # ── 新聞催化劑 ────────────────────────────────────────────────────────
    lines.append("### 新聞催化劑\n")
    for t, items in news_map.items():
        if t in research_tickers:
            continue  # 已在深入研究區段列出
        inf  = info.get(t, {})
        name = inf.get("name", t)
        rev  = inf.get("revenue_growth")
        rev_s = f"，營收 {rev*100:+.0f}%" if rev is not None else ""

        row_match = final[final["ticker"] == t]
        if row_match.empty:
            continue
        row = row_match.iloc[0]

        lines.append(f"#### {t}　{name}")
        lines.append(
            f"今日漲幅 **{row['return_1d']:+.1f}%**，"
            f"近 5 日 **{row['return_5d']:+.1f}%**"
            f"{rev_s}　｜　評分 {row['score']:.3f}\n"
        )
        translated = _translate_news(items)
        if translated:
            for item in translated:
                title  = item.get("title", "")
                source = item.get("source", "")
                url    = item.get("url", "")
                if title:
                    src_link = f"[{source}]({url})" if url else source
                    date_prefix = f"({item.get('date')}) " if item.get("date") else ""
                    lines.append(f"- {date_prefix}{title} *— {src_link}*")
        else:
            lines.append("- 目前無最新新聞")
        lines.append("")

    lines.append("---\n")

    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"{today.strftime('%Y-%m-%d')}.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    _update_index()
    console.print(f"\n[dim]報告已儲存 → {report_path}[/dim]")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    console.print(Rule("[bold blue]Growth Screener — 強勢中大型股篩選[/bold blue]"))

    console.print("\n[dim]Step 1/4[/dim] 取得股票清單...", end=" ")
    tickers = get_universe()
    console.print(f"[green]{len(tickers)} 支[/green]")

    console.print("[dim]Step 2/4[/dim] 下載歷史資料（約 1–2 分鐘）...")
    close, volume = fetch_historical(tickers)

    console.print("[dim]Step 3/4[/dim] 計算技術指標...")
    candidates = screen(close, volume)

    if candidates.empty:
        console.print("[yellow]今日無符合條件的股票。[/yellow]")
        return

    top = candidates.head(TOP_N)

    console.print(f"[dim]Step 4/4[/dim] 取得 [cyan]{len(top)}[/cyan] 支候選股基本面資料...")
    info = fetch_ticker_info(top["ticker"].tolist())

    # 基本面分類：移除 / 需深入研究 / 正常通過
    passed    = []
    flags_map = {}
    removed   = []

    for _, row in top.iterrows():
        t   = row["ticker"]
        flg = get_fundamental_flags(info.get(t, {}))
        flags_map[t] = flg
        if flg["remove"]:
            removed.append((t, flg["concern_str"]))
        else:
            passed.append(row)

    if removed:
        console.print(f"\n[dim]已移除 {len(removed)} 支（分析師共識強力賣出）：[/dim]")
        for t, reason in removed:
            console.print(f"  [red]✗[/red] [bold]{t}[/bold] {info.get(t,{}).get('name',t)} — {reason}")

    if not passed:
        console.print("\n[yellow]篩選後無剩餘候選股。[/yellow]")
        return

    final = pd.DataFrame(passed).reset_index(drop=True)

    # ── 終端表格 ──────────────────────────────────────────────────────────
    table = Table(
        title=f"\n研究候選股（共 {len(final)} 支）",
        show_lines=True,
        header_style="bold white on dark_blue",
    )
    table.add_column("#",       width=3,  justify="right", style="dim")
    table.add_column("代號",    width=8,  style="bold cyan")
    table.add_column("公司",    max_width=20)
    table.add_column("產業",    max_width=14, style="dim")
    table.add_column("股價",    justify="right")
    table.add_column("日漲",    justify="right")
    table.add_column("5日",     justify="right")
    table.add_column("10日",    justify="right")
    table.add_column("↑/5d",   justify="right")
    table.add_column("基期",    justify="right")
    table.add_column("均線",    justify="right")
    table.add_column("RSI",     justify="right")
    table.add_column("評分",    justify="right")
    table.add_column("營收",    justify="right")
    table.add_column("FCF",     justify="right")
    table.add_column("評等",    justify="right")
    table.add_column("P/E",     justify="right")
    table.add_column("市值",    justify="right")

    for i, row in enumerate(final.itertuples(), 1):
        t   = row.ticker
        inf = info.get(t, {})
        flg = flags_map.get(t, {})

        def _r(v):
            return f"[green]+{v:.1f}%[/green]" if v > 0 else f"[red]{v:.1f}%[/red]"

        ma_str = (("↑" if row.ma20_rising else "·")
                  + ("50" if row.above_ma50 else "··")
                  + ("✦" if row.ma_golden else ""))

        rsi_s = f"[yellow]{row.rsi}[/yellow]" if row.rsi > 75 else str(row.rsi)

        badges = (" ★" if row.near_52w_high else "") + (" 🔍" if flg.get("needs_research") else "")

        eps_fwd = inf.get("eps_forward")
        eps_ttm = inf.get("eps_trailing")
        eps_arr = (" [green]↑[/green]" if eps_fwd and eps_ttm and eps_fwd > eps_ttm
                   else " [red]↓[/red]" if eps_fwd and eps_ttm and eps_fwd < eps_ttm
                   else "")

        table.add_row(
            str(i),
            t + badges,
            (inf.get("name") or t)[:20],
            (inf.get("sector") or "")[:14],
            f"${row.price:,.2f}",
            _r(row.return_1d),
            _r(row.return_5d),
            _r(row.return_10d),
            f"{row.consec_up}/5",
            f"[cyan]{row.base_depth:.1f}%[/cyan]",
            ma_str,
            rsi_s,
            f"{row.score:.2f}",
            _fmt_rev(inf.get("revenue_growth")),
            _fmt_fcf(inf.get("free_cashflow")) + eps_arr,
            _fmt_rec(inf.get("recommendation")),
            _fmt_pe(inf.get("pe_forward")),
            _fmt_cap(inf.get("market_cap", 0)),
        )

    console.print(table)
    console.print(
        "[dim]★=接近52週高點  🔍=基本面需驗證  "
        "↑=MA20上升  50=站上MA50  ✦=黃金排列  "
        "基期=距6個月高點的距離[/dim]"
    )

    # 說明 🔍 標記的原因
    research_tickers = [t for t, flg in flags_map.items() if flg.get("needs_research") and t in final["ticker"].values]
    if research_tickers:
        console.print()
        for t in research_tickers:
            inf = info.get(t, {})
            flg = flags_map[t]
            console.print(
                f"  [yellow]🔍[/yellow]  [bold]{t}[/bold] {inf.get('name', t)} — "
                f"{flg['concern_str']}。技術面已突破，建議查看近期新聞確認轉型題材。"
            )

    # ── 新聞（一般 + 深入研究） ───────────────────────────────────────────
    # 一般：前 NEWS_TOP_N；深入研究：無論排名都顯示
    news_display = list(dict.fromkeys(
        list(final["ticker"].head(NEWS_TOP_N)) + research_tickers
    ))

    console.print(Rule("\n[bold]新聞催化劑[/bold]"))
    news_map = {}
    for t in news_display:
        row_match = final[final["ticker"] == t]
        if row_match.empty:
            continue
        row = row_match.iloc[0]
        inf = info.get(t, {})
        flg = flags_map.get(t, {})
        name = inf.get("name", t)
        rev  = inf.get("revenue_growth")
        rev_s = f"，營收 {rev*100:+.0f}%" if rev is not None else ""

        label = "[yellow]🔍 需深入研究[/yellow] " if flg.get("needs_research") else ""
        console.print(
            f"\n{label}[bold cyan]{t}[/bold cyan] — {name}  "
            f"([green]+{row['return_1d']:.1f}%[/green] 今日{rev_s})"
        )

        items = fetch_news(t)
        news_map[t] = items
        if items:
            for item in items:
                title  = item.get("title", "")
                source = item.get("source", "")
                if title:
                    console.print(f"  • {title}  [dim]— {source}[/dim]")
        else:
            console.print("  [dim]目前無最新新聞。[/dim]")

    console.print()

    # ── 寫入每日報告 ──────────────────────────────────────────────────────
    _write_daily_report(date.today(), final, info, flags_map, removed, news_map)


if __name__ == "__main__":
    main()
