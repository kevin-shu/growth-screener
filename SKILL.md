---
name: growth-screener
description: >
  Runs the daily Growth Screener to identify strong large-cap momentum candidates
  from S&P 500 + NASDAQ-100, then produces a per-stock AI analysis report.
  Invoke when the user asks to run the daily screen, generate today's report,
  or analyze screener output.
compatibility: Requires Python 3.9+, packages in requirements.txt, project root as working directory
metadata:
  author: Kevin Shu
  version: "1.0"
allowed-tools: Bash Read Write Edit Agent
---

## Instructions

When this skill is invoked, execute the following steps in order.

### Step 1 — Read investment thoughts

Read `thoughts.md`. This file is the source of truth for how to run this screener.
Extract and internalize:
- **排除名單**：tickers to filter out before top-N selection
- **長期觀察名單**：tickers to pay extra attention to even if their score is lower
- **投資偏好**：any stated preferences that should shape the AI commentary focus

Then sync the exclusion list into `screener/blacklist.json` (overwrite) so the script picks it up:

```json
{
  "TICKER": "reason",
  ...
}
```

### Step 2 — Run the screener

```bash
python3 scripts/main.py
```

Wait for it to complete. The script filters `blacklist.json` before selecting top N,
then saves today's report to `daily-reports/YYYY-MM-DD.md`.

### Step 3 — Read the report

Read the full `daily-reports/YYYY-MM-DD.md`. It contains:
- **篩選結果** table — passing stocks with technical + fundamental metrics
- **需深入研究** — stocks with fundamental concerns (🔍)
- **新聞催化劑** — recent news headlines per stock

Also check `thoughts.md` for any **長期觀察名單** stocks that might have appeared
in today's results — flag them prominently in the analysis if so.

### Step 4 — Spawn one sub-agent per stock (all in parallel)

For every stock in the 篩選結果 table, spawn a sub-agent using the Agent tool.
Launch **all sub-agents in a single message** so they run in parallel.

Each sub-agent receives a self-contained prompt with:
- The stock's row data from the 篩選結果 table (all numeric metrics)
- Its 🔍 concern details from 需深入研究 (if flagged)
- Its news items from 新聞催化劑
- Any relevant notes from `thoughts.md` (e.g. watchlist, user preferences)

Each sub-agent must return a **繁體中文** analysis of 3–5 sentences covering:
1. **技術面解讀** — why this signal stands out (cite score, RSI, MA structure, streak)
2. **基本面評估** — whether fundamentals support the move (revenue trend, FCF, analyst rating, PE)
3. **催化劑 / 風險** — what the news headlines reveal; for 🔍 stocks, explicitly judge whether the headlines constitute a credible turnaround thesis

Rules for sub-agents:
- Reference actual numbers from the data (e.g., 評分 0.847、RSI 68、營收 +22%)
- For ★ stocks: address whether the 52-week high proximity is a breakout or an overextension risk
- For 🔍 stocks: state clearly whether news supports or undermines a reversal thesis
- No bullet points — write flowing prose

### Step 5 — Rewrite the report

After all sub-agents complete, use the Edit tool to replace everything from
`### 需深入研究` (or `### 🔍`) through the end of the `### 新聞催化劑` section
(up to and including the final `---`) with a new unified section:

```markdown
### 個股分析報告

#### 1. [TICKER](https://www.tradingview.com/symbols/TICKER/)　公司名稱　[badges]

{sub-agent commentary for this stock}

**新聞**
- (MM/DD) 標題 — [來源](url)
- ...

---

#### 2. [TICKER](https://www.tradingview.com/symbols/TICKER/)　公司名稱　[badges]
...
```

Include every stock from the 篩選結果 table, in the same order.
For stocks without news, omit the **新聞** block.
Preserve the 已移除 section if it exists (do not overwrite it).

### Step 6 — Launch the report viewer

```bash
bash report.sh
```

This starts the HTTP server and opens today's report in the browser.

### Step 7 — Commit and push to GitHub

After all edits are complete (report rewritten, thoughts.md updated), commit and push:

```bash
git add daily-reports/ screener/blacklist.json thoughts.md
git commit -m "feat: daily report $(date +%Y-%m-%d)"
git push
```

### Step 8 — Ask for feedback and update thoughts.md

Ask the user:

> 報告完成了。看完之後有什麼想法嗎？例如：
> - 有哪些股票覺得不需要追蹤（可以加到排除名單）？
> - 有哪些覺得很有潛力、想長期觀察？
> - 對分析方向有任何偏好或調整？

After the user responds, update `thoughts.md`:
- Add new exclusions to the **排除名單** table
- Add watchlist additions to **長期觀察名單**
- Append a new entry to **Feedback 歷史** with today's date and a concise summary of the user's thoughts

Keep `thoughts.md` as a living document that grows over time.
