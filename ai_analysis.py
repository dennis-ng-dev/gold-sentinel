"""
AI Analysis — Gold Sentinel
- Gemini 2.0 Flash + Google Search Grounding: crawl tin tức vàng VN & thế giới
- Claude Haiku: tổng hợp phân tích + gợi ý hành động
"""
import os
import json
import requests
from datetime import datetime, timezone, timedelta

VN_TZ = timezone(timedelta(hours=7))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


def fetch_news_gemini(gold_price: float, sjc_buy: float) -> str:
    """Dùng Gemini 2.0 Flash + Google Search Grounding để lấy tin tức vàng."""
    if not GEMINI_API_KEY:
        return ""

    prompt = f"""Tìm kiếm tin tức MỚI NHẤT trong 24 giờ qua về thị trường vàng.

Giá hiện tại: XAU/USD ${gold_price:,.0f} | SJC {sjc_buy}tr/lượng

Tìm kiếm và tóm tắt:
1. Tin tức vàng thế giới: Fed, USD, lạm phát, địa chính trị, ETF vàng
2. Tin tức vàng Việt Nam: NHNN, SJC, nhu cầu trong nước

Trả lời bằng tiếng Việt, ngắn gọn, mỗi tin 1-2 câu. Tối đa 5 tin quan trọng nhất."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.3}
    }

    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code != 200:
            print(f"  Gemini error {r.status_code}: {r.text[:200]}")
            return ""
        data = r.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if "text" in p)
        return text.strip()
    except Exception as e:
        print(f"  Gemini exception: {e}")
        return ""


def analyze_with_claude(gold_price: float, change_pct: float, sjc_buy: float,
                        sjc_sell: float, news: str, action_hint: str) -> str:
    """Dùng Claude Haiku để tổng hợp phân tích + gợi ý hành động."""
    if not ANTHROPIC_API_KEY:
        return ""

    now_str = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M")

    system = """Bạn là chuyên gia phân tích thị trường vàng với 20 năm kinh nghiệm.
Nhiệm vụ: phân tích ngắn gọn, thực tế, hữu ích cho nhà đầu tư cá nhân Việt Nam.
Phong cách: trực tiếp, không hoa mỹ, có số liệu cụ thể.
Ngôn ngữ: tiếng Việt."""

    user = f"""Thời điểm: {now_str}

DỮ LIỆU GIÁ:
- XAU/USD: ${gold_price:,.1f} (thay đổi: {change_pct:+.1f}%)
- SJC: Mua {sjc_buy}tr / Bán {sjc_sell}tr VNĐ/lượng
- Tín hiệu kỹ thuật: {action_hint}

TIN TỨC MỚI NHẤT:
{news if news else "(Không có tin tức)"}

Hãy viết phân tích ngắn gọn gồm 3 phần:

📰 TIN TỨC NỔI BẬT
(2-3 điểm quan trọng nhất ảnh hưởng đến giá vàng)

🧠 NHẬN ĐỊNH
(tác động ngắn hạn 1-3 ngày, xu hướng)

🎯 GỢI Ý
(hành động cụ thể: mua/bán/giữ/chờ và ở mức giá nào)

Giới hạn: tối đa 200 chữ. Không cần disclaimer."""

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": "claude-haiku-4-5",
        "max_tokens": 512,
        "system": system,
        "messages": [{"role": "user", "content": user}]
    }

    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers=headers, json=payload, timeout=30)
        if r.status_code != 200:
            print(f"  Claude error {r.status_code}: {r.text[:200]}")
            return ""
        data = r.json()
        content = data.get("content", [])
        text = "".join(c.get("text", "") for c in content if c.get("type") == "text")
        return text.strip()
    except Exception as e:
        print(f"  Claude exception: {e}")
        return ""


def get_ai_analysis(gold: dict, sjc: dict, action_hint: str) -> str:
    """
    Main entry point. Trả về block AI analysis để append vào Telegram report.
    gold: {"price": ..., "change_pct": ...}
    sjc:  {"buy": ..., "sell": ...}  hoặc None
    action_hint: chuỗi gợi ý từ analyze() trong gold_sentinel_bot.py
    """
    if not ANTHROPIC_API_KEY and not GEMINI_API_KEY:
        return ""

    price = gold.get("price", 0)
    change_pct = gold.get("change_pct", 0)
    sjc_buy = sjc.get("buy", 0) if sjc else 0
    sjc_sell = sjc.get("sell", 0) if sjc else 0

    print("  🔍 Gemini: đang tìm tin tức...")
    news = fetch_news_gemini(price, sjc_buy)
    if news:
        print(f"  ✅ Gemini: {len(news)} ký tự")
    else:
        print("  ⚠️ Gemini: không lấy được tin")

    print("  🤖 Claude: đang phân tích...")
    analysis = analyze_with_claude(price, change_pct, sjc_buy, sjc_sell, news, action_hint)
    if analysis:
        print(f"  ✅ Claude: {len(analysis)} ký tự")
    else:
        print("  ⚠️ Claude: không lấy được phân tích")
        return ""

    return f"\n━━━━━━━━━━━━━━━━━━━━\n🤖 <b>PHÂN TÍCH AI</b>\n\n{analysis}\n━━━━━━━━━━━━━━━━━━━━"
