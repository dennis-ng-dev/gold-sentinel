# Gold Sentinel

Tool theo dõi giá vàng thế giới và trong nước, gửi cảnh báo qua Telegram.

## Kiến trúc

```
fetch_prices.py          ← Chạy mỗi 15 phút (cron-job.org + GitHub Actions), lưu data
gold_sentinel_bot.py     ← Build & gửi báo cáo Telegram
ai_analysis.py           ← Gemini crawl tin tức + Claude Haiku phân tích (chạy 2 lần/ngày)
run_daily.py             ← Entry point cho GitHub Actions (gửi Telegram)
docs/index.html          ← Dashboard (GitHub Pages)
data/prices.json         ← Data store duy nhất
```

`fetch_prices_v3.py` và `gold_sentinel_bot_v3.py` là file cũ, không dùng nữa.

## Data flow

1. **cron-job.org** trigger GitHub Actions workflow đúng giờ mỗi 15 phút (thay vì dùng GitHub cron bị delay)
2. `fetch_prices.py` fetch giá → lưu vào `data/prices.json` → commit + push
3. Dashboard `docs/index.html` đọc `prices.json` từ raw GitHub URL, auto-refresh 15 phút
4. Telegram gửi 2 lần/ngày: 8h sáng (01 UTC) và 8h tối (13 UTC) — chỉ khi `TELEGRAM_PAUSED != true`

## Cron Schedule

### cron-job.org (trigger chính, đáng tin cậy hơn GitHub cron)
- **Weekdays** (T2-T6): mỗi 15 phút tại :00/:15/:30/:45 (giờ VN) — Job ID: `7404119`
- **Weekend** (T7-CN): mỗi 2 tiếng tại giờ chẵn (giờ VN) — Job ID: `7404120`

### GitHub Actions workflow (`.github/workflows/gold-sentinel.yml`)
- Schedule backup: `*/15 * * * 1-5` (weekdays), `0 */2 * * 0,6` (weekends)
- `workflow_dispatch` với input `send_telegram=true/false`

## Nguồn dữ liệu

| Dữ liệu | Nguồn | Interval |
|---|---|---|
| XAU/USD realtime (dashboard) | TradingView widget `PEPPERSTONE:XAUUSD` | Realtime (browser) |
| XAU/USD cho biểu đồ/data | `api.gold-api.com/price/XAU` (free, no key) | 15 phút |
| XAU/USD backup | `goldapi.io` (key: `GOLD_API_KEY` secret) | fallback |
| Giá SJC trong nước | `sjc.com.vn/GoldPrice/Services/PriceService.ashx` | Mỗi lần chạy (real) |
| Daily history 30 ngày | `stooq.com/q/d/l/?s=xauusd&i=d` (free, no key) | Mỗi lần chạy |

SJC fetch mỗi lần (không cache), POST với `method=GetCurrentGoldPricesByBranch&BranchId=1`.

## prices.json schema

```json
{
  "latest": {
    "timestamp": "ISO8601+07:00",
    "slot": "2026-03-23T11:00",      // snap về :00 hoặc :30
    "date": "2026-03-23",
    "price": 4369.1,                 // XAU/USD
    "change": 0, "change_pct": 0,
    "high": 0, "low": 0,
    "source": "gold-api.com",
    "sjc_buy": 164.0,                // triệu VNĐ/lượng
    "sjc_sell": 167.0,
    "sjc_real": true,                // false = ước tính
    "sjc_updated": "09:58 23/03/2026"
  },
  "history": [...],   // intraday records, snap :00/:30, giữ 90 ngày
  "daily": [...]      // 1 record/ngày, merge stooq + history
}
```

## GitHub Secrets

| Secret | Dùng cho |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Gửi tin nhắn Telegram |
| `TELEGRAM_CHAT_ID` | ID chat/group nhận tin (group 1) |
| `TELEGRAM_CHAT_ID_2` | ID supergroup thứ hai (`-1003822795065`) |
| `GOLD_API_KEY` | goldapi.io (backup world price) |
| `ANTHROPIC_API_KEY` | Claude Haiku 4.5 — phân tích thị trường |
| `GEMINI_API_KEY` | Gemini 2.5 Flash — crawl tin tức (Google Search) |

## GitHub Variables

| Variable | Giá trị | Dùng cho |
|---|---|---|
| `TELEGRAM_PAUSED` | `true` / `false` | Pause/resume gửi Telegram tự động |

Khi `TELEGRAM_PAUSED=true`: cron tự động không gửi, nhưng manual trigger (`workflow_dispatch` với `send_telegram=true`) vẫn gửi bình thường.

## Dashboard

URL: `https://dennis-ng-dev.github.io/gold-sentinel/`

- XAU/USD: TradingView widget realtime (`PEPPERSTONE:XAUUSD`), không gọi API từ GitHub Pages domain
- SJC: đọc từ `prices.json` (proxy qua GitHub raw, không lộ domain)
- Biểu đồ: 2 tab — Intraday (snap :00/:30) và Daily (30 ngày từ stooq)
- Tooltip hover: hiển thị XAU price + SJC buy/sell nếu có data tương ứng
- Auto-refresh: 15 phút (với cache-bust `?t=Date.now()`)

## Telegram Logic

- Gửi **2 lần/ngày**: 01:00 UTC (8h sáng VN) và 13:00 UTC (8h tối VN)
- Check phút `M < 10` để tránh gửi lại lúc :15/:30/:45 trong cùng giờ
- `TELEGRAM_CHAT_ID_2` là supergroup ID (group bị nâng cấp từ `-796204684` → `-1003822795065`)

## Mức giá quan trọng

```python
PRICE_LEVELS = {
    "all_time_high": 5595,        # 29/01/2026
    "resistance_5000": 5000,
    "support_4550": 4550,
    "support_4360": 4360,
    "bear_line_200ema": 4200,
}
```

Logic cảnh báo: phân biệt **đã thủng** vs **đang test** — không dùng `<=` đơn thuần, luôn kèm giá hiện tại trong alert text.

## FOMC 2026

Lãi suất hiện tại: 3.50–3.75%

| Ngày | SEP |
|---|---|
| 29/04 | |
| 17/06 | ✓ DOT PLOT |
| 29/07 | |
| 16/09 | ✓ DOT PLOT |
| 28/10 | |
| 09/12 | ✓ DOT PLOT |

## AI Analysis Flow

`ai_analysis.py` chạy khi gửi Telegram (2 lần/ngày):

1. **Gemini 2.5 Flash** + Google Search → crawl tin tức vàng VN & thế giới 24h qua
   - Fallback model list: `gemini-2.5-flash` → `gemini-2.5-flash-lite` → `gemini-2.5-pro`
2. **Claude Haiku 4.5** → tổng hợp → block `🤖 PHÂN TÍCH AI` trong Telegram message
   - Output: 3 phần — 📰 Tin tức nổi bật / 🧠 Nhận định / 🎯 Gợi ý
   - Giới hạn 200 chữ, tối đa 512 tokens

`build_daily_report(with_ai=True)` trong `gold_sentinel_bot.py` để bật AI.
`build_daily_report(with_ai=False)` (default) để tắt — dùng khi test.

## Snap to Slot

Timestamps snap về :00 hoặc :30 để chart gọn:
- minute < 15 → snap :00
- 15 ≤ minute < 45 → snap :30
- minute ≥ 45 → snap :00 giờ tiếp theo
