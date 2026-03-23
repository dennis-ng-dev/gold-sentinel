#!/bin/bash
set -e
echo "⬙ Gold Sentinel — Update v3: SJC thật từ sjc.com.vn"
echo ""

if [ ! -d ".git" ]; then
    echo "❌ cd gold-sentinel trước!"
    exit 1
fi

# Tìm thư mục chứa file download
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Copy fetch_prices
if [ -f "$SCRIPT_DIR/fetch_prices_v3.py" ]; then
    cp "$SCRIPT_DIR/fetch_prices_v3.py" fetch_prices.py
    echo "  ✅ fetch_prices.py v3"
elif [ -f "fetch_prices_v3.py" ]; then
    cp fetch_prices_v3.py fetch_prices.py
    echo "  ✅ fetch_prices.py v3"
else
    echo "  ❌ Không tìm thấy fetch_prices_v3.py"
    echo "     Đặt file cùng thư mục với script này hoặc trong gold-sentinel/"
    exit 1
fi

# Copy bot
if [ -f "$SCRIPT_DIR/gold_sentinel_bot_v3.py" ]; then
    cp "$SCRIPT_DIR/gold_sentinel_bot_v3.py" gold_sentinel_bot.py
    echo "  ✅ gold_sentinel_bot.py v3"
elif [ -f "gold_sentinel_bot_v3.py" ]; then
    cp gold_sentinel_bot_v3.py gold_sentinel_bot.py
    echo "  ✅ gold_sentinel_bot.py v3"
else
    echo "  ⚠️ Không tìm thấy gold_sentinel_bot_v3.py — giữ nguyên bot cũ"
fi

echo ""
echo "🚀 Pushing..."
git add -A
git commit -m "🏦 v3: giá SJC thật từ sjc.com.vn"
git pull --rebase
git push

echo ""
echo "✅ Done!"
echo "  🏦 SJC: sjc.com.vn/giavang/textContent.php (realtime)"
echo "  🪙 World: gold-api.com (unlimited free)"
echo "  📱 Telegram: ✅ = giá thật, 📊 = ước tính"
echo ""
echo "  🧪 Test: gh workflow run gold-sentinel.yml -f send_telegram=true"
