#!/bin/bash
# ============================================================
# ⬙ GOLD SENTINEL — Update: thêm hourly fetch + dashboard
# ============================================================
# Chạy trong thư mục gold-sentinel đã có sẵn
# ============================================================

set -e

echo ""
echo "⬙ Gold Sentinel — Nâng cấp hourly fetch + dashboard"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Kiểm tra đang ở trong repo
if [ ! -d ".git" ]; then
    echo "❌ Không tìm thấy git repo! Chạy lệnh này trong thư mục gold-sentinel:"
    echo "   cd gold-sentinel && bash update.sh"
    exit 1
fi

# ------- Xóa workflow cũ -------
rm -f .github/workflows/daily-report.yml
echo "  🗑️  Xóa workflow cũ"

# ------- Tạo data folder -------
mkdir -p data
cat > data/prices.json << 'EOF'
{"history": [], "latest": null, "daily": [], "updated_at": null, "total_records": 0}
EOF
echo "  ✅ data/prices.json"

# ------- Tạo fetch_prices.py -------
cat > fetch_prices.py << 'PYEOF'
"""
GOLD SENTINEL — Price Fetcher
Fetch giá vàng từ nhiều nguồn miễn phí, lưu vào data/prices.json
"""
import os, json, requests
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PRICES_FILE = os.path.join(DATA_DIR, "prices.json")
MAX_HISTORY_DAYS = 90
GOLD_API_KEY = os.getenv("GOLD_API_KEY", "")
USD_VND_RATE = 26339
SJC_PREMIUM = 28_000_000

def fetch_from_gold_api_free():
    try:
        resp = requests.get("https://api.gold-api.com/price/XAU", timeout=10)
        if resp.status_code != 200: return None
        d = resp.json()
        p = d.get("price", 0)
        if p == 0: return None
        return {"price": p, "change": d.get("change",0), "change_pct": d.get("changePercentage",0),
                "high": d.get("high",0), "low": d.get("low",0), "source": "gold-api.com"}
    except Exception as e:
        print(f"  gold-api.com error: {e}"); return None

def fetch_from_goldapi_io():
    if not GOLD_API_KEY: return None
    try:
        resp = requests.get("https://www.goldapi.io/api/XAU/USD",
                          headers={"x-access-token": GOLD_API_KEY}, timeout=10)
        if resp.status_code != 200: return None
        d = resp.json()
        p = d.get("price", 0)
        if p == 0: return None
        return {"price": p, "change": d.get("ch",0), "change_pct": d.get("chp",0),
                "high": d.get("high_price",0), "low": d.get("low_price",0), "source": "goldapi.io"}
    except Exception as e:
        print(f"  goldapi.io error: {e}"); return None

def fetch_gold_price():
    for fn, name in [(fetch_from_gold_api_free, "gold-api.com"), (fetch_from_goldapi_io, "goldapi.io")]:
        print(f"  Trying {name}...")
        r = fn()
        if r: return r
    return None

def calc_sjc(p):
    w = p * USD_VND_RATE * 37.5 / 31.1035
    return {"buy": round((w + SJC_PREMIUM - 3e6) / 1e6, 1), "sell": round((w + SJC_PREMIUM) / 1e6, 1)}

def load_prices():
    if not os.path.exists(PRICES_FILE): return {"history": [], "latest": None}
    try:
        with open(PRICES_FILE) as f: return json.load(f)
    except: return {"history": [], "latest": None}

def save_prices(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PRICES_FILE, "w") as f: json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    vn = timezone(timedelta(hours=7))
    now = datetime.now(vn)
    print(f"⬙ Price Fetch — {now.strftime('%Y-%m-%d %H:%M')} VN")

    gold = fetch_gold_price()
    if not gold: print("  ❌ Fetch failed!"); return False
    print(f"  ✅ ${gold['price']:,.1f} ({gold['source']})")

    sjc = calc_sjc(gold["price"])
    data = load_prices()

    rec = {"timestamp": now.isoformat(), "date": now.strftime("%Y-%m-%d"), "hour": now.hour,
           "price": gold["price"], "change": gold["change"], "change_pct": gold["change_pct"],
           "high": gold["high"], "low": gold["low"],
           "sjc_buy": sjc["buy"], "sjc_sell": sjc["sell"], "source": gold["source"]}

    data["latest"] = rec
    hist = data.get("history", [])

    dup = False
    for h in hist:
        if h.get("date") == rec["date"] and h.get("hour") == rec["hour"]:
            h.update(rec); dup = True; break
    if not dup: hist.append(rec)

    cutoff = (now - timedelta(days=MAX_HISTORY_DAYS)).isoformat()
    hist = [h for h in hist if h["timestamp"] >= cutoff]

    daily = {}
    for h in hist:
        d = h["date"]
        if d not in daily or h["timestamp"] > daily[d]["timestamp"]: daily[d] = h

    data["history"] = hist
    data["daily"] = sorted(daily.values(), key=lambda x: x["date"])
    data["updated_at"] = now.isoformat()
    data["total_records"] = len(hist)

    save_prices(data)
    print(f"  💾 Saved ({len(hist)} records, {len(data['daily'])} days)")
    return True

if __name__ == "__main__": main()
PYEOF
echo "  ✅ fetch_prices.py"

# ------- Tạo workflow mới -------
rm -f .github/workflows/daily-report.yml
cat > .github/workflows/gold-sentinel.yml << 'EOF'
name: Gold Sentinel

on:
  schedule:
    - cron: '5 * * * 1-5'
    - cron: '5 */6 * * 0,6'
  workflow_dispatch:
    inputs:
      send_telegram:
        description: 'Gửi Telegram?'
        required: false
        default: 'false'
        type: choice
        options: ['true', 'false']

jobs:
  fetch-and-report:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install requests python-dotenv

      - name: Fetch gold price
        env:
          GOLD_API_KEY: ${{ secrets.GOLD_API_KEY }}
        run: python fetch_prices.py

      - name: Commit price data
        run: |
          git config user.name "Gold Sentinel Bot"
          git config user.email "bot@gold-sentinel"
          git add data/
          git diff --cached --quiet || git commit -m "📊 $(date -u +'%Y-%m-%d %H:%M UTC')"
          git push

      - name: Check if should send Telegram
        id: tg
        run: |
          H=$(date -u +'%H')
          M="${{ github.event.inputs.send_telegram }}"
          if [ "$H" = "01" ] || [ "$H" = "13" ] || [ "$M" = "true" ]; then
            echo "send=true" >> $GITHUB_OUTPUT
          else
            echo "send=false" >> $GITHUB_OUTPUT
          fi

      - name: Send Telegram report
        if: steps.tg.outputs.send == 'true'
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GOLD_API_KEY: ${{ secrets.GOLD_API_KEY }}
        run: python run_daily.py
EOF
echo "  ✅ .github/workflows/gold-sentinel.yml"

# ------- Commit & push -------
echo ""
echo "🚀 Pushing to GitHub..."
git add -A
git commit -m "🔄 Upgrade: hourly price fetch + JSON storage"
git push

echo ""
echo "✅ Done! Workflow mới sẽ:"
echo "   • Fetch giá mỗi giờ (T2-T6)"
echo "   • Fetch mỗi 6h (cuối tuần)"
echo "   • Lưu vào data/prices.json"
echo "   • Gửi Telegram 8h sáng + 8h tối VN"
echo ""
echo "📊 Dashboard đọc data từ:"
echo "   https://raw.githubusercontent.com/$(gh repo view --json owner -q .owner.login)/gold-sentinel/main/data/prices.json"
echo ""
echo "🧪 Test ngay: gh workflow run gold-sentinel.yml -f send_telegram=true"
echo ""
