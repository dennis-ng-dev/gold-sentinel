"""
GOLD SENTINEL — Telegram Bot
=============================
Gửi báo cáo giá vàng + phân tích Fed hàng ngày qua Telegram.
Cảnh báo khi biến động lớn (>2%).
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================
# CẤU HÌNH
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")
GOLD_API_KEY = os.getenv("GOLD_API_KEY", "")
METALS_API_KEY = os.getenv("METALS_API_KEY", "")

ALERT_THRESHOLD_PCT = 2.0
ALERT_THRESHOLD_USD = 100
USD_VND_RATE = 26339

# ============================================================
# LỊCH FOMC 2026
# ============================================================
FOMC_SCHEDULE = [
    {"date": "2026-01-28", "status": "done", "decision": "Hold 3.50-3.75%", "has_sep": False},
    {"date": "2026-03-18", "status": "done", "decision": "Hold 3.50-3.75%", "has_sep": True},
    {"date": "2026-04-29", "status": "upcoming", "decision": None, "has_sep": False},
    {"date": "2026-06-17", "status": "upcoming", "decision": None, "has_sep": True},
    {"date": "2026-07-29", "status": "upcoming", "decision": None, "has_sep": False},
    {"date": "2026-09-16", "status": "upcoming", "decision": None, "has_sep": True},
    {"date": "2026-10-28", "status": "upcoming", "decision": None, "has_sep": False},
    {"date": "2026-12-09", "status": "upcoming", "decision": None, "has_sep": True},
]

PRICE_LEVELS = {
    "all_time_high": 5595,
    "resistance_5000": 5000,
    "support_4550": 4550,
    "support_4360": 4360,
    "bear_line_200ema": 4200,
}

BANK_TARGETS = {
    "J.P. Morgan": 6300,
    "UBS": 6200,
    "Goldman Sachs": 5400,
    "Deutsche Bank": 6000,
    "Scotiabank": 4100,
}

# ============================================================
# LẤY GIÁ VÀNG
# ============================================================

def fetch_gold_price_goldapi():
    try:
        headers = {"x-access-token": GOLD_API_KEY}
        resp = requests.get("https://www.goldapi.io/api/XAU/USD", headers=headers, timeout=10)
        data = resp.json()
        return {
            "price": data.get("price", 0),
            "prev_close": data.get("prev_close_price", 0),
            "change": data.get("ch", 0),
            "change_pct": data.get("chp", 0),
            "high_24h": data.get("high_price", 0),
            "low_24h": data.get("low_price", 0),
            "source": "GoldAPI",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"GoldAPI error: {e}")
        return None

def fetch_gold_price():
    if GOLD_API_KEY:
        result = fetch_gold_price_goldapi()
        if result:
            return result

    try:
        resp = requests.get("https://api.gold-api.com/price/XAU", timeout=10)
        data = resp.json()
        return {
            "price": data.get("price", 0),
            "prev_close": data.get("previousClose", 0),
            "change": data.get("change", 0),
            "change_pct": data.get("changePercentage", 0),
            "high_24h": data.get("high", 0),
            "low_24h": data.get("low", 0),
            "source": "GoldAPI-Free",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Free API error: {e}")
        return None

def fetch_sjc_price():
    gold = fetch_gold_price()
    if not gold:
        return None
    world_price_vnd = gold["price"] * USD_VND_RATE * 37.5 / 31.1035
    sjc_premium = 28_000_000
    return {
        "buy": round((world_price_vnd + sjc_premium - 3_000_000) / 1_000_000, 1),
        "sell": round((world_price_vnd + sjc_premium) / 1_000_000, 1),
        "world_equivalent": round(world_price_vnd / 1_000_000, 1),
        "premium": round(sjc_premium / 1_000_000, 1),
    }

# ============================================================
# PHÂN TÍCH THỊ TRƯỜNG
# ============================================================

def analyze_market(price_data):
    price = price_data["price"]
    change_pct = price_data.get("change_pct", 0)
    alerts = []
    action = ""
    action_emoji = ""

    if price <= PRICE_LEVELS["bear_line_200ema"]:
        action = "CHỜ — Dưới 200-EMA, rủi ro bear market"
        action_emoji = "🔴"
        alerts.append("⚠️ DƯỚI 200-EMA ($4,200) — Ranh giới Bear Market!")
    elif price <= PRICE_LEVELS["support_4360"]:
        action = "QUAN SÁT — Vùng hỗ trợ mạnh, chờ tín hiệu đảo chiều"
        action_emoji = "🟠"
        alerts.append("🟡 Vùng hỗ trợ mạnh $4,360 — Có thể là đáy")
    elif price <= PRICE_LEVELS["support_4550"]:
        action = "CÂN NHẮC — Có thể mua DCA đợt 1 (20-30% vốn)"
        action_emoji = "🟡"
        alerts.append("🟡 Vùng hỗ trợ $4,550 đang bị test")
    elif price < PRICE_LEVELS["resistance_5000"]:
        action = "MUA DCA — Chia nhỏ nhiều đợt, tích lũy dần"
        action_emoji = "🔵"
        alerts.append("📊 Dưới $5,000 — Vùng tích lũy")
    else:
        action = "GIỮ — Uptrend xác nhận, không bán vội"
        action_emoji = "🟢"
        alerts.append("✅ Trên $5,000 — Xu hướng tăng")

    if abs(change_pct) > ALERT_THRESHOLD_PCT:
        direction = "tăng" if change_pct > 0 else "giảm"
        alerts.append(f"🔥 Biến động BẤT THƯỜNG: {direction} {abs(change_pct):.1f}% trong 24h!")

    today = datetime.now()
    next_fomc = None
    days_to_fomc = None
    for m in FOMC_SCHEDULE:
        meeting_date = datetime.strptime(m["date"], "%Y-%m-%d")
        if meeting_date > today:
            next_fomc = m
            days_to_fomc = (meeting_date - today).days
            if days_to_fomc <= 3:
                alerts.append(f"🚨 FOMC HỌP TRONG {days_to_fomc} NGÀY — Biến động cực cao!")
            elif days_to_fomc <= 7:
                alerts.append(f"⏰ FOMC họp trong {days_to_fomc} ngày — Cẩn thận!")
            elif days_to_fomc <= 14:
                alerts.append(f"📅 FOMC sắp họp ({days_to_fomc} ngày)")
            break

    upside_jpm = ((BANK_TARGETS["J.P. Morgan"] - price) / price * 100)
    upside_gs = ((BANK_TARGETS["Goldman Sachs"] - price) / price * 100)

    return {
        "action": action,
        "action_emoji": action_emoji,
        "alerts": alerts,
        "next_fomc": next_fomc,
        "days_to_fomc": days_to_fomc,
        "upside_jpm": upside_jpm,
        "upside_gs": upside_gs,
        "distance_from_ath": ((PRICE_LEVELS["all_time_high"] - price) / PRICE_LEVELS["all_time_high"] * 100),
    }

# ============================================================
# GỬI TIN NHẮN TELEGRAM
# ============================================================

def send_telegram(message, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"[{datetime.now()}] Telegram sent OK")
            return True
        else:
            print(f"[{datetime.now()}] Telegram error: {resp.text}")
            return False
    except Exception as e:
        print(f"[{datetime.now()}] Telegram send failed: {e}")
        return False

# ============================================================
# TẠO BÁO CÁO
# ============================================================

def build_daily_report():
    gold = fetch_gold_price()
    if not gold or gold["price"] == 0:
        return "⚠️ Không thể lấy dữ liệu giá vàng. Thử lại sau."

    sjc = fetch_sjc_price()
    analysis = analyze_market(gold)

    price = gold["price"]
    change = gold.get("change", 0)
    change_pct = gold.get("change_pct", 0)
    change_icon = "🟢 ▲" if change >= 0 else "🔴 ▼"

    today_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    msg = f"""⬙ <b>GOLD SENTINEL</b> — {today_str}
━━━━━━━━━━━━━━━━━━━━

🪙 <b>XAU/USD:</b> ${price:,.1f} {change_icon} {abs(change):.1f} ({change_pct:+.1f}%)"""

    if gold.get("high_24h") and gold.get("low_24h"):
        msg += f"\n   H: ${gold['high_24h']:,.1f} | L: ${gold['low_24h']:,.1f}"

    if sjc:
        msg += f"""

🏦 <b>SJC (ước tính):</b>
   Mua: {sjc['buy']}tr | Bán: {sjc['sell']}tr
   Premium: ~{sjc['premium']}tr vs thế giới"""

    msg += f"""

━━━━━━━━━━━━━━━━━━━━
📊 <b>Mốc kỹ thuật:</b>
   Kháng cự: $5,000
   Hỗ trợ 1: $4,550 | HT 2: $4,360
   Bear line: $4,200 (200-EMA)
   Từ ATH ($5,595): -{analysis['distance_from_ath']:.1f}%

━━━━━━━━━━━━━━━━━━━━"""

    if analysis["alerts"]:
        msg += "\n🔔 <b>Cảnh báo:</b>\n"
        for alert in analysis["alerts"]:
            msg += f"   {alert}\n"

    if analysis["next_fomc"]:
        fomc_date = datetime.strptime(analysis['next_fomc']['date'], '%Y-%m-%d').strftime('%d/%m')
        sep_tag = " 📈 DOT PLOT" if analysis['next_fomc'].get('has_sep') else ""
        msg += f"""
━━━━━━━━━━━━━━━━━━━━
📅 <b>FOMC tiếp:</b> {fomc_date} ({analysis['days_to_fomc']}d){sep_tag}
   Lãi suất: 3.50-3.75%"""

    msg += f"""

━━━━━━━━━━━━━━━━━━━━
{analysis['action_emoji']} <b>GỢI Ý:</b> {analysis['action']}

📈 Upside: JPM ($6,300) <b>{analysis['upside_jpm']:+.1f}%</b> | GS ($5,400) <b>{analysis['upside_gs']:+.1f}%</b>

━━━━━━━━━━━━━━━━━━━━
<i>⚠️ Không phải tư vấn tài chính.</i>"""

    return msg


def send_fomc_reminder():
    today = datetime.now()
    for m in FOMC_SCHEDULE:
        meeting_date = datetime.strptime(m["date"], "%Y-%m-%d")
        days_until = (meeting_date - today).days

        if days_until == 1:
            sep = "📈 Phiên có DOT PLOT — Cực kỳ quan trọng!" if m.get('has_sep') else "📋 Phiên thường"
            msg = f"""🚨 <b>FOMC HỌP NGÀY MAI!</b>

📅 Ngày: {meeting_date.strftime('%d/%m/%Y')}
{sep}
⏰ Kết quả: ~2:00 AM giờ VN

<b>Lưu ý:</b>
• Không mua/bán trước phiên họp
• Chờ kết quả + họp báo Powell
• Biến động 3-5% là bình thường

<i>⚠️ Không phải tư vấn tài chính.</i>"""
            send_telegram(msg)
            break

        if days_until == 7:
            msg = f"""📅 <b>FOMC họp trong 1 tuần</b>

📆 {meeting_date.strftime('%d/%m/%Y')}
{"📈 Phiên có DOT PLOT" if m.get('has_sep') else "📋 Phiên thường"}

Chuẩn bị: Xem xét lại vị thế.

<i>⚠️ Không phải tư vấn tài chính.</i>"""
            send_telegram(msg)
            break
