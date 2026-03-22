#!/bin/bash
set -e

echo "⬙ Gold Sentinel — Upgrade: fetch mỗi 15 phút"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ ! -d ".git" ]; then
    echo "❌ cd gold-sentinel trước!"
    exit 1
fi

# ------- Workflow: 15 phút -------
cat > .github/workflows/gold-sentinel.yml << 'EOF'
name: Gold Sentinel

on:
  schedule:
    - cron: '*/15 * * * 1-5'
    - cron: '0 */2 * * 0,6'
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
          M=$(date -u +'%M')
          MANUAL="${{ github.event.inputs.send_telegram }}"
          if ([ "$H" = "01" ] && [ "$M" -lt "15" ]) || ([ "$H" = "13" ] && [ "$M" -lt "15" ]) || [ "$MANUAL" = "true" ]; then
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
echo "  ✅ Workflow: mỗi 15 phút (T2-T6), 2h (T7-CN)"

# ------- Dashboard: refresh 15 phút -------
sed -i '' 's/5\*60\*1000/15*60*1000/g' docs/index.html 2>/dev/null || sed -i 's/5\*60\*1000/15*60*1000/g' docs/index.html
sed -i '' 's/60\*60\*1000/15*60*1000/g' docs/index.html 2>/dev/null || sed -i 's/60\*60\*1000/15*60*1000/g' docs/index.html
sed -i '' 's/Auto-refresh [0-9]* phút/Auto-refresh 15 phút/g' docs/index.html 2>/dev/null || sed -i 's/Auto-refresh [0-9]* phút/Auto-refresh 15 phút/g' docs/index.html
echo "  ✅ Dashboard: refresh 15 phút"

# ------- Push -------
git add -A
git commit -m "⚡ fetch every 15min (unlimited free API)"
git pull --rebase
git push

echo ""
echo "✅ Done!"
echo ""
echo "  📊 Fetch: mỗi 15 phút (T2-T6)"
echo "  🌐 Dashboard refresh: 15 phút"
echo "  📱 Telegram: 8h + 20h (không đổi)"
echo "  💰 GitHub Actions: ~48 phút/ngày (free: 66 phút/ngày)"
echo ""
