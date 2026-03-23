#!/bin/bash
set -e
echo "⬙ Fix Telegram timing..."

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

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
          MANUAL="${{ github.event.inputs.send_telegram }}"
          echo "Current UTC hour: $H"
          echo "Manual trigger: $MANUAL"
          # 01 UTC = 8h sáng VN, 13 UTC = 8h tối VN
          if [ "$H" = "01" ] || [ "$H" = "13" ] || [ "$MANUAL" = "true" ]; then
            echo "send=true" >> $GITHUB_OUTPUT
            echo ">>> Will send Telegram"
          else
            echo "send=false" >> $GITHUB_OUTPUT
            echo ">>> Skip Telegram (not 01 or 13 UTC)"
          fi

      - name: Send Telegram report
        if: steps.tg.outputs.send == 'true'
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GOLD_API_KEY: ${{ secrets.GOLD_API_KEY }}
        run: python run_daily.py
EOF

git add .github/workflows/gold-sentinel.yml
git commit -m "fix: simplify Telegram send timing (hour only)"
git pull --rebase
git push

echo ""
echo "✅ Fixed! Test ngay:"
echo "   gh workflow run gold-sentinel.yml -f send_telegram=true"
echo ""
echo "Telegram sẽ tự gửi lúc:"
echo "   01:00-01:15 UTC = 8h sáng VN"
echo "   13:00-13:15 UTC = 8h tối VN"
