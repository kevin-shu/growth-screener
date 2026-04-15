# Todo

## DONE

- [x] 建立股票宇宙（S&P500 + NASDAQ-100，Wikipedia 抓取）
  => 完成 screener/universe.py，加入 User-Agent header 解決 403 問題

- [x] 批次下載歷史 OHLCV 資料
  => 完成 screener/data.py，使用 yfinance.download() 批次下載

- [x] v1 技術篩選：單日百分位 + RVOL
  => 回測勝率 61.7%，RVOL 在大盤普漲日會過濾掉正確標的

- [x] v2 技術篩選：加入基期低指標，移除 RVOL 硬篩選
  => 回測勝率 66.2%，信號數從 180 增加到 855

- [x] v3 技術篩選：5日累積漲幅百分位 + 連續上漲天數 + MA20 突破
  => 回測勝率 68.1%，平均 3M +9.8%，alpha +1.2%

- [x] 新增基本面過濾層（死貓跳偵測）
  => 三分類：移除 / ⚠保留警告 / 正常通過
  => ⚠ 條件：基本面差但已回到 52W 高點（如 INTC 轉型題材）

- [x] 回測機制（backtest.py）
  => 2 年資料、每週篩選、+63 交易日報酬 vs SPY

- [x] 撰寫 SKILL.md 記錄設計決策與學習

- [x] 報告改為獨立檔案（daily-reports/YYYY-MM-DD.md）+ 網頁閱讀器（index.html）
  => 每日報告儲存於 daily-reports/，自動維護 index.json；index.html 提供左側月份導覽、右側 Markdown 渲染

## TODO

- [ ] 財報日標記：未來兩週內有財報的股票加上 📅 提示
- [ ] 市場環境判斷：SPY > SPY_MA50 才輸出信號（熊市保護）
- [ ] 5 日累積成交量：用 5 日總量比 20 日均量，取代單日 RVOL
- [ ] 產業強度：同產業 ETF 是否也在上漲（減少個股誤判）
