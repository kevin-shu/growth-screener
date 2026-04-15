#!/usr/bin/env bash
# 啟動 Growth Screener 網頁閱讀器
cd "$(dirname "$0")"
PORT=8765

# 若 port 已被佔用則先結束舊程序
lsof -ti tcp:$PORT | xargs kill -9 2>/dev/null

python3 -m http.server $PORT &>/tmp/screener-server.log &
echo "伺服器啟動中 (port $PORT)..."
sleep 0.5

URL="http://localhost:$PORT"
# 優先用 Google Chrome 開啟（避免 Safari 快取問題）；沒有 Chrome 則用系統預設
if open -a "Google Chrome" "$URL" 2>/dev/null; then
  echo "已在 Chrome 開啟 $URL"
else
  open "$URL"
  echo "已開啟 $URL"
fi
