---
name: growth-screener
description: >
  Runs the daily Growth Screener to identify strong large-cap momentum candidates
  from S&P 500 + NASDAQ-100, then provides AI commentary for each result.
  Invoke when the user asks to run the daily screen, generate today's report,
  or analyze screener output.
compatibility: Requires Python 3.9+, packages in requirements.txt, project root as working directory
metadata:
  author: Kevin Shu
  version: "1.0"
allowed-tools: Bash Read
---

## Instructions

When this skill is invoked, execute the following steps in order.

### 1. Run the screener

```bash
python3 scripts/main.py
```

Wait for it to complete. The script will print a progress table in the terminal
and save the report to `daily-reports/YYYY-MM-DD.md`.

### 2. Read the report

Read the generated `daily-reports/YYYY-MM-DD.md` (use today's date).

### 3. Provide AI commentary for each stock

For every stock listed in the **篩選結果** table, output a commentary block in
Traditional Chinese using this format:

```
### AI 評論：{TICKER}　{公司名稱}
{2–4 sentences}
```

Each commentary must address:

1. **技術面** — 說明這支股票評分高的原因（哪些指標突出：5日漲幅百分位、均線結構、連漲天數等）
2. **基本面** — 判斷基本面是否支撐這波漲勢（營收成長、FCF、分析師評等、本益比是否合理）
3. **催化劑或風險** — 根據報告中的新聞標題，指出最值得關注的催化劑或主要風險

**額外規則：**
- 數字要具體，直接引用報告中的數值（例如：評分 0.847、RSI 68、營收 +22%）
- 標有 🔍 的股票，必須明確判斷新聞是否構成可信的反轉題材
- 標有 ★ 的股票，說明接近 52 週高點對這筆交易的意義（突破還是追高風險）
- 不要重複表格中已有的資料，重點放在「這些數字代表什麼」的解讀
