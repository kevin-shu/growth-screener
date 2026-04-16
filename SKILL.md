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
allowed-tools: Bash Read Edit Agent
---

## Instructions

When this skill is invoked, execute the following steps in order.

### Step 1 — Run the screener

```bash
python3 scripts/main.py
```

Wait for it to complete. The script saves today's report to
`daily-reports/YYYY-MM-DD.md` (use today's date).

### Step 2 — Read the report

Read the full `daily-reports/YYYY-MM-DD.md`. It contains:
- **篩選結果** table — all passing stocks with technical + fundamental metrics
- **需深入研究** — stocks with fundamental concerns (🔍)
- **新聞催化劑** — recent news headlines per stock

### Step 3 — Spawn one sub-agent per stock (all in parallel)

For every stock in the 篩選結果 table, spawn a sub-agent using the Agent tool.
Launch **all sub-agents in a single message** so they run in parallel.

Each sub-agent receives a self-contained prompt with:
- The stock's row data from the 篩選結果 table (all numeric metrics)
- Its 🔍 concern details from 需深入研究 (if flagged)
- Its news items from 新聞催化劑

Each sub-agent must return a **繁體中文** analysis of 3–5 sentences covering:
1. **技術面解讀** — why this signal stands out (cite score, RSI, MA structure, streak)
2. **基本面評估** — whether fundamentals support the move (revenue trend, FCF, analyst rating, PE)
3. **催化劑 / 風險** — what the news headlines reveal; for 🔍 stocks, explicitly judge whether the headlines constitute a credible turnaround thesis

Rules for sub-agents:
- Reference actual numbers from the data (e.g., 評分 0.847、RSI 68、營收 +22%)
- For ★ stocks: address whether the 52-week high proximity is a breakout or an overextension risk
- For 🔍 stocks: state clearly whether news supports or undermines a reversal thesis
- No bullet points — write flowing prose

### Step 4 — Rewrite the report

After all sub-agents complete, use the Edit tool to replace everything from
`### 需深入研究` (or `### 🔍`) through the end of the `### 新聞催化劑` section
(up to and including the final `---`) with a new unified section:

```markdown
### 個股分析報告

#### 1. TICKER　公司名稱　[badges]

{sub-agent commentary for this stock}

**新聞**
- (MM/DD) 標題 — [來源](url)
- ...

---

#### 2. TICKER　公司名稱　[badges]
...
```

Include every stock from the 篩選結果 table, in the same order.
For stocks without news, omit the **新聞** block.
Preserve the 已移除 section if it exists (do not overwrite it).
