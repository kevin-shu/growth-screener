---
name: growth-screener
description: >
  Daily stock screener for large-cap growth candidates (S&P 500 + NASDAQ-100).
  Runs technical + fundamental filters to narrow 500+ tickers to ~15–25 research
  candidates, fetches news and fundamentals, generates a Markdown report, then
  collaborates with an AI agent to provide per-stock commentary.
  Use when the user wants to run the daily screen, view past reports, or get
  AI-assisted analysis of screener output.
compatibility: Requires Python 3.9+, pip packages in requirements.txt, ANTHROPIC_API_KEY env var
metadata:
  author: Kevin Shu
  version: "1.0"
allowed-tools: Bash Read Write
---

## Overview

Growth Screener is a two-phase daily workflow:

1. **Script phase** — `scripts/main.py` runs fully automated:
   technical filters → fundamental filters → news fetch → Markdown report saved to `daily-reports/YYYY-MM-DD.md`

2. **AI collaboration phase** — after the report is generated, an AI agent reads
   it and provides per-stock commentary (see [Step 3](#step-3-ai-commentary) below).

For detailed design decisions, scoring formula, and backtest methodology, see
[doc/REFERENCE.md](doc/REFERENCE.md).

---

## Step 1 — Run the daily screen

```bash
# One-command: starts HTTP server + opens browser
bash report.sh

# Or run the screener directly
python3 scripts/main.py
```

The script outputs a Rich table in the terminal and saves the report to
`daily-reports/YYYY-MM-DD.md`. It also updates `daily-reports/index.json`
so the web viewer picks it up automatically.

**Typical runtime:** 2–4 minutes (bulk yfinance download is the bottleneck).

---

## Step 2 — View the report

Open `http://localhost:8765` after running `bash report.sh`.
The web viewer (`index.html`) loads the latest report automatically.

Report columns at a glance:

| Column | Meaning |
|--------|---------|
| ★ | Price within 5% of 52-week high |
| 🔍 | Fundamental concern — verify the thesis |
| 基期 | Depth from 6-month high before this rally (deeper = more room) |
| 連漲/5 | Positive-return days out of last 5 |
| 評分 | Composite score (5D rank ×0.35 + base ×0.25 + streak ×0.20 + MA ×0.20) |

---

## Step 3 — AI commentary

After the report is generated, read `daily-reports/YYYY-MM-DD.md` and for each
stock in the screener results table, provide a commentary block covering:

1. **技術面解讀** — why this signal is notable (score drivers, MA structure)
2. **基本面評估** — whether fundamentals support the move (revenue trend, FCF, analyst rating)
3. **催化劑 / 風險** — key news catalyst or risk to watch based on the fetched headlines

**Format per stock:**

```
### AI 評論：{TICKER}
{2–3 sentences in Traditional Chinese}
```

**Guidelines:**
- Be specific — reference the actual numbers from the report (e.g., score, RSI, revenue growth %)
- For 🔍-flagged stocks, explicitly address whether the news headlines provide a credible turnaround thesis
- Keep each commentary to 2–4 sentences; brevity is preferred

---

## Step 4 — Backtest (optional)

```bash
python3 scripts/backtest.py
```

Simulates weekly screens over 2 years of history and reports 3-month forward
returns vs. SPY. Takes ~10 minutes.

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/main.py` | Daily screener entry point |
| `scripts/backtest.py` | Historical validation |

## Key modules

| Module | Purpose |
|--------|---------|
| `screener/universe.py` | Fetch S&P 500 + NASDAQ-100 tickers from Wikipedia |
| `screener/data.py` | Bulk OHLCV download via yfinance |
| `screener/signals.py` | Technical indicators + scoring |
| `screener/info.py` | Fundamentals + dead-cat-bounce filter |
| `screener/news.py` | Yahoo Finance news fetch |
