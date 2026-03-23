# Gold Sentinel

Tool theo dõi giá vàng thế giới và trong nước, gửi cảnh báo qua Telegram.

## Kiến trúc

```
fetch_prices.py          ← Chạy mỗi 15 phút (GitHub Actions), lưu data
gold_sentinel_bot.py     ← Build & gửi báo cáo Telegram
ai_analysis.py           ← Gemini crawl tin tức + Claude phân tích (chạy 2 lần/ngày)
run_daily.py             ← Entry point cho GitHub Actions (gửi Telegram)
docs/index.html          ← Dashboard (GitHub Pages)
data/prices.json         ← Data store duy nhất
```

`fetch_prices_v3.py` và `gold_sentinel_bot_v3.py` là file cũ, không dùng nữa.

## Data flow

1. GitHub Actions chạy `fetch_prices.py` mỗi 15 phút (ngày thường), 2 tiếng (cuối tuần)
2. `fetch_prices.py` lưu vào `data/prices.json` rồi commit + push
3. Dashboard `docs/index.html` đọc `prices.json` từ raw GitHub URL
4. Telegram gửi 2 lần/ngày: 8h sáng (01 UTC) và 8h tối (13 UTC)

## Nguồn dữ liệu

| Dữ liệu | Nguồn | Interval |
|---|---|---|
| XAU/USD realtime (dashboard) | TradingView widget `PEPPERSTONE:XAUUSD` | Realtime (browser) |
| XAU/USD cho biểu đồ/data | `api.gold-api.com/price/XAU` (free, no key) | 30 phút |
| XAU/USD backup | `goldapi.io` (key: `GOLD_API_KEY` secret) | fallback |
| Giá SJC trong nước | `sjc.com.vn/GoldPrice/Services/PriceService.ashx` | 2 tiếng |
| Daily history 30 ngày | `stooq.com/q/d/l/?s=xauusd&i=d` (free, no key) | Mỗi lần chạy |

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
| `TELEGRAM_CHAT_ID` | ID chat nhận tin |
| `TELEGRAM_CHAT_ID_2` | ID group thứ hai |
| `GOLD_API_KEY` | goldapi.io (backup world price) |
| `ANTHROPIC_API_KEY` | Claude Haiku — tổng hợp phân tích |
| `GEMINI_API_KEY` | Gemini 2.0 Flash — crawl tin tức (Google Search Grounding) |

## Dashboard

URL: `https://dennis-ng-dev.github.io/gold-sentinel/`

- XAU/USD: TradingView widget realtime, không gọi API từ domain này
- SJC: đọc từ `prices.json` (proxy qua GitHub, không lộ domain)
- Biểu đồ: 2 tab — Intraday (15-30 phút/point) và Daily (30 ngày từ stooq)
- Tooltip hover: giá XAU + SJC tương ứng
- Auto-refresh: 15 phút

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

Logic cảnh báo: phân biệt **đã thủng** vs **đang test** — không dùng `<=` đơn thuần.

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

`ai_analysis.py` chạy khi gửi Telegram (2 lần/ngày: 8h sáng, 8h tối VN):
1. **Gemini 2.0 Flash** + Google Search Grounding → tìm tin tức vàng 24h qua
2. **Claude Haiku** → tổng hợp → block `🤖 PHÂN TÍCH AI` trong Telegram message

`build_daily_report(with_ai=True)` trong `gold_sentinel_bot.py` để bật AI.
`build_daily_report(with_ai=False)` (default) để tắt — dùng khi test.
