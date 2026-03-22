"""
GOLD SENTINEL — Telegram Bot (v2)
==================================
Ưu tiên free API, goldapi.io chỉ là backup.
"""
import os, json, requests
from datetime import datetime, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
GOLD_API_KEY = os.getenv("GOLD_API_KEY", "")

ALERT_THRESHOLD_PCT = 2.0
USD_VND_RATE = 26339
SJC_PREMIUM = 28_000_000

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
    "all_time_high": 5595, "resistance_5000": 5000,
    "support_4550": 4550, "support_4360": 4360, "bear_line_200ema": 4200,
}

BANK_TARGETS = {"J.P. Morgan": 6300, "UBS": 6200, "Goldman Sachs": 5400, "Deutsche Bank": 6000}

# ---- API: free trước, paid sau ----

def fetch_free():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10)
        if r.status_code != 200: return None
        d = r.json(); p = d.get("price", 0)
        if p == 0: return None
        return {"price": p, "change": d.get("change",0), "change_pct": d.get("changePercentage",0),
                "high_24h": d.get("high",0), "low_24h": d.get("low",0), "source": "gold-api.com"}
    except: return None

def fetch_paid():
    if not GOLD_API_KEY: return None
    try:
        r = requests.get("https://www.goldapi.io/api/XAU/USD",
                        headers={"x-access-token": GOLD_API_KEY}, timeout=10)
        if r.status_code != 200: return None
        d = r.json(); p = d.get("price", 0)
        if p == 0: return None
        return {"price": p, "change": d.get("ch",0), "change_pct": d.get("chp",0),
                "high_24h": d.get("high_price",0), "low_24h": d.get("low_price",0), "source": "goldapi.io"}
    except: return None

def fetch_gold_price():
    return fetch_free() or fetch_paid()

def calc_sjc(p):
    w = p * USD_VND_RATE * 37.5 / 31.1035
    return {"buy": round((w+SJC_PREMIUM-3e6)/1e6,1), "sell": round((w+SJC_PREMIUM)/1e6,1), "premium": round(SJC_PREMIUM/1e6,1)}

# ---- Phân tích ----

def analyze_market(gold):
    p = gold["price"]; cpct = gold.get("change_pct",0)
    alerts = []; act = ""; emoji = ""

    if p <= PRICE_LEVELS["bear_line_200ema"]:
        act = "CHỜ — Dưới 200-EMA, rủi ro bear market"; emoji = "🔴"
        alerts.append("⚠️ DƯỚI 200-EMA ($4,200) — Bear Market!")
    elif p <= PRICE_LEVELS["support_4360"]:
        act = "QUAN SÁT — Vùng hỗ trợ mạnh, chờ đảo chiều"; emoji = "🟠"
        alerts.append("🟡 Hỗ trợ mạnh $4,360 — Có thể là đáy")
    elif p <= PRICE_LEVELS["support_4550"]:
        act = "CÂN NHẮC — Mua DCA đợt 1 (20-30% vốn)"; emoji = "🟡"
        alerts.append("🟡 Hỗ trợ $4,550 đang bị test")
    elif p < PRICE_LEVELS["resistance_5000"]:
        act = "MUA DCA — Chia nhỏ nhiều đợt"; emoji = "🔵"
        alerts.append("📊 Dưới $5,000 — Vùng tích lũy")
    else:
        act = "GIỮ — Uptrend xác nhận"; emoji = "🟢"
        alerts.append("✅ Trên $5,000 — Xu hướng tăng")

    if abs(cpct) > ALERT_THRESHOLD_PCT:
        d = "tăng" if cpct > 0 else "giảm"
        alerts.append(f"🔥 BẤT THƯỜNG: {d} {abs(cpct):.1f}% trong 24h!")

    today = datetime.now(); nf = None; dtf = None
    for m in FOMC_SCHEDULE:
        md = datetime.strptime(m["date"], "%Y-%m-%d")
        if md > today:
            nf = m; dtf = (md - today).days
            if dtf <= 3: alerts.append(f"🚨 FOMC TRONG {dtf} NGÀY!")
            elif dtf <= 7: alerts.append(f"⏰ FOMC trong {dtf} ngày")
            elif dtf <= 14: alerts.append(f"📅 FOMC sắp họp ({dtf} ngày)")
            break

    ath = PRICE_LEVELS["all_time_high"]
    return {"action": act, "emoji": emoji, "alerts": alerts,
            "next_fomc": nf, "days_to_fomc": dtf,
            "upside_jpm": (BANK_TARGETS["J.P. Morgan"]-p)/p*100,
            "upside_gs": (BANK_TARGETS["Goldman Sachs"]-p)/p*100,
            "from_ath": (ath-p)/ath*100}

# ---- Telegram ----

def send_telegram(msg, parse_mode="HTML"):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                         json={"chat_id": TELEGRAM_CHAT_ID, "text": msg,
                               "parse_mode": parse_mode, "disable_web_page_preview": True}, timeout=10)
        ok = r.status_code == 200
        print(f"[{datetime.now()}] Telegram {'OK' if ok else 'FAIL: '+r.text}")
        return ok
    except Exception as e:
        print(f"[{datetime.now()}] Telegram error: {e}"); return False

def build_daily_report():
    gold = fetch_gold_price()
    if not gold or gold["price"] == 0:
        return "⚠️ Không lấy được giá vàng. Thử lại sau."

    sjc = calc_sjc(gold["price"]); a = analyze_market(gold)
    p = gold["price"]; ch = gold.get("change",0); cpct = gold.get("change_pct",0)
    icon = "🟢 ▲" if ch >= 0 else "🔴 ▼"
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    msg = f"""⬙ <b>GOLD SENTINEL</b> — {now}
━━━━━━━━━━━━━━━━━━━━

🪙 <b>XAU/USD:</b> ${p:,.1f} {icon} {abs(ch):.1f} ({cpct:+.1f}%)"""

    if gold.get("high_24h") and gold.get("low_24h"):
        msg += f"\n   H: ${gold['high_24h']:,.1f} | L: ${gold['low_24h']:,.1f}"

    msg += f"""

🏦 <b>SJC (ước tính):</b> {sjc['buy']}tr / {sjc['sell']}tr

━━━━━━━━━━━━━━━━━━━━
📊 <b>Mốc kỹ thuật:</b>
   Kháng cự: $5,000
   HT1: $4,550 | HT2: $4,360
   Bear: $4,200 (200-EMA)
   Từ ATH: -{a['from_ath']:.1f}%
━━━━━━━━━━━━━━━━━━━━"""

    if a["alerts"]:
        msg += "\n🔔 <b>Cảnh báo:</b>\n"
        for al in a["alerts"]: msg += f"   {al}\n"

    if a["next_fomc"]:
        fd = datetime.strptime(a['next_fomc']['date'],'%Y-%m-%d').strftime('%d/%m')
        sep = " 📈 DOT PLOT" if a['next_fomc'].get('has_sep') else ""
        msg += f"\n📅 <b>FOMC:</b> {fd} ({a['days_to_fomc']}d){sep}"

    msg += f"""

━━━━━━━━━━━━━━━━━━━━
{a['emoji']} <b>GỢI Ý:</b> {a['action']}

📈 JPM ($6,300) <b>{a['upside_jpm']:+.1f}%</b> | GS ($5,400) <b>{a['upside_gs']:+.1f}%</b>
━━━━━━━━━━━━━━━━━━━━
<i>⚠️ Không phải tư vấn tài chính.</i>
🔗 <i>Nguồn: {gold['source']}</i>"""
    return msg

def send_fomc_reminder():
    today = datetime.now()
    for m in FOMC_SCHEDULE:
        md = datetime.strptime(m["date"], "%Y-%m-%d")
        d = (md - today).days
        if d == 1:
            sep = "📈 DOT PLOT — Cực kỳ quan trọng!" if m.get('has_sep') else "📋 Phiên thường"
            send_telegram(f"""🚨 <b>FOMC HỌP NGÀY MAI!</b>

📅 {md.strftime('%d/%m/%Y')}
{sep}
⏰ Kết quả: ~2:00 AM VN

• Không mua/bán trước phiên
• Chờ kết quả + họp báo
• Biến động 3-5% bình thường

<i>⚠️ Không phải tư vấn tài chính.</i>""")
            break
        if d == 7:
            send_telegram(f"""📅 <b>FOMC trong 1 tuần</b>
📆 {md.strftime('%d/%m/%Y')} {"📈 DOT PLOT" if m.get('has_sep') else "📋 Thường"}
Chuẩn bị: xem lại vị thế.
<i>⚠️ Không phải tư vấn tài chính.</i>""")
            break
