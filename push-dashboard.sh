#!/bin/bash
set -e
echo "⬙ Updating dashboard..."

if [ ! -d ".git" ]; then
    echo "❌ cd gold-sentinel trước!"
    exit 1
fi

# Download the new dashboard
# Copy the content below into docs/index.html, or run:
# cp <path-to-downloaded-dashboard-full.html> docs/index.html

git add docs/index.html
git diff --cached --quiet && echo "Không có thay đổi" && exit 0
git commit -m "✨ Full dashboard: tabs, FOMC, scenarios, targets"
git pull --rebase
git push

echo ""
echo "✅ Dashboard updated!"
echo "🌐 https://dennis-ng-dev.github.io/gold-sentinel/"
echo ""
echo "Nếu chưa bật Pages: Settings → Pages → main /docs"
