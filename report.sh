#!/usr/bin/env bash
# 啟動 Growth Screener 網頁閱讀器
cd "$(dirname "$0")"
PORT=8765

# 若 port 已被佔用則先結束舊程序
lsof -ti tcp:$PORT | xargs kill -9 2>/dev/null

python3 -m http.server $PORT --directory . &>/tmp/screener-server.log &
echo "伺服器啟動中 (port $PORT)..."
sleep 0.5

URL="http://localhost:$PORT"
open "$URL"
echo "已開啟 $URL"
