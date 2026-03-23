"""
GOLD SENTINEL — Telegram Bot v3
- Giá SJC thật từ sjc.com.vn/GoldPrice/Services/PriceService.ashx
- Free API first cho giá thế giới, fallback goldapi.io
- Timezone VN (UTC+7)
"""
import os, json, requests
from datetime import datetime, timezone, timedelta

VN_TZ = timezone(timedelta(hours=7))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_ID_2 = os.getenv("TELEGRAM_CHAT_ID_2", "")
GOLD_API_KEY = os.getenv("GOLD_API_KEY", "")
ALERT_THRESHOLD_PCT = 2.0

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
PRICE_LEVELS = {"all_time_high": 5595, "resistance_5000": 5000, "support_4550": 4550, "support_4360": 4360, "bear_line_200ema": 4200}
BANK_TARGETS = {"J.P. Morgan": 6300, "UBS": 6200, "Goldman Sachs": 5400, "Deutsche Bank": 6000}

# ---- World price ----
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
        r = requests.get("https://www.goldapi.io/api/XAU/USD", headers={"x-access-token": GOLD_API_KEY}, timeout=10)
        if r.status_code != 200: return None
        d = r.json(); p = d.get("price", 0)
        if p == 0: return None
        return {"price": p, "change": d.get("ch",0), "change_pct": d.get("chp",0),
                "high_24h": d.get("high_price",0), "low_24h": d.get("low_price",0), "source": "goldapi.io"}
    except: return None

def fetch_gold_price():
    return fetch_free() or fetch_paid()

# ---- SJC real price ----
def fetch_sjc():
    try:
        r = requests.post(
            "https://sjc.com.vn/GoldPrice/Services/PriceService.ashx",
            data={"method": "GetCurrentGoldPricesByBranch", "BranchId": "1"},
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://sjc.com.vn/gia-vang-online"},
            timeout=10
        )
        if r.status_code != 200: return None
        d = r.json()
        if not d.get("success") or not d.get("data"): return None
        for item in d["data"]:
            name = item.get("TypeName", "").upper()
            if "1L" in name or "10L" in name or "1KG" in name:
                buy = round(item["BuyValue"] / 1e6, 1)
                sell = round(item["SellValue"] / 1e6, 1)
                if buy > 50 and sell > 50:
                    return {"buy": buy, "sell": sell, "real": True,
                            "updated": d.get("latestDate", "")}
    except: pass
    return None

def get_sjc(world_price=0):
    result = fetch_sjc()
    if result: return result
    if world_price:
        w = world_price * 26339 * 37.5 / 31.1035
        return {"buy": round((w+25e6)/1e6,1), "sell": round((w+28e6)/1e6,1), "real": False}
    return None

# ---- Analysis ----
def analyze(gold):
    p = gold["price"]; cpct = gold.get("change_pct",0)
    alerts = []; act = ""; emoji = ""
    L = PRICE_LEVELS
    if p <= L["bear_line_200ema"]:
        act="CHỜ — Dưới 200-EMA ($4,200), rủi ro bear market"; emoji="🔴"
        alerts.append(f"⚠️ THỦNG 200-EMA — Giá ${p:,.0f} dưới $4,200!")
    elif p <= L["support_4360"]:
        act="QUAN SÁT — Đã thủng $4,360, chờ tín hiệu phục hồi"; emoji="🟠"
        alerts.append(f"🟠 Đã thủng hỗ trợ $4,360 — Giá ${p:,.0f}, vùng nguy hiểm")
        if p > L["bear_line_200ema"] + 50:
            alerts.append(f"⚠️ Tiếp theo: 200-EMA $4,200 — cần giữ vững")
    elif p <= L["support_4550"]:
        act="CÂN NHẮC — Đã thủng $4,550, đang trong vùng $4,360–$4,550"; emoji="🟡"
        alerts.append(f"🟡 Đã thủng hỗ trợ $4,550 — Giá ${p:,.0f}")
        dist = p - L["support_4360"]
        if dist < 50:
            alerts.append(f"⚠️ Sắp test $4,360 — còn cách ${dist:.0f}")
    elif p < L["resistance_5000"]:
        act="MUA DCA — Dưới $5,000, vùng tích lũy"; emoji="🔵"
        dist = L["support_4550"] - p
        if dist > 0:
            alerts.append(f"📊 Dưới $5,000 — Hỗ trợ $4,550 phía dưới ${dist:.0f}")
        else:
            alerts.append(f"📊 Dưới $5,000 — Vùng tích lũy, đang test $4,550")
    else:
        act="GIỮ — Uptrend xác nhận, trên $5,000"; emoji="🟢"
        alerts.append(f"✅ Trên $5,000 — Xu hướng tăng")
    if abs(cpct) > ALERT_THRESHOLD_PCT:
        alerts.append(f"🔥 BẤT THƯỜNG: {'tăng' if cpct>0 else 'giảm'} {abs(cpct):.1f}%!")
    today = datetime.now(VN_TZ); nf = None; dtf = None
    for m in FOMC_SCHEDULE:
        md = datetime.strptime(m["date"], "%Y-%m-%d").replace(tzinfo=VN_TZ)
        if md > today:
            nf=m; dtf=(md-today).days
            if dtf<=3: alerts.append(f"🚨 FOMC TRONG {dtf} NGÀY!")
            elif dtf<=7: alerts.append(f"⏰ FOMC trong {dtf} ngày")
            elif dtf<=14: alerts.append(f"📅 FOMC sắp họp ({dtf}d)")
            break
    ath = PRICE_LEVELS["all_time_high"]
    return {"action":act,"emoji":emoji,"alerts":alerts,"next_fomc":nf,"days_to_fomc":dtf,
            "upside_jpm":(BANK_TARGETS["J.P. Morgan"]-p)/p*100,
            "upside_gs":(BANK_TARGETS["Goldman Sachs"]-p)/p*100,
            "from_ath":(ath-p)/ath*100}

# ---- Telegram ----
def send_telegram(msg, parse_mode="HTML"):
    chat_ids = [cid for cid in [TELEGRAM_CHAT_ID, TELEGRAM_CHAT_ID_2] if cid]
    ok = True
    for cid in chat_ids:
        try:
            r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                             json={"chat_id":cid,"text":msg,"parse_mode":parse_mode,"disable_web_page_preview":True}, timeout=10)
            sent = r.status_code == 200
            print(f"[{datetime.now()}] Telegram {cid} {'OK' if sent else 'FAIL: '+r.text}")
            ok = ok and sent
        except Exception as e:
            print(f"[{datetime.now()}] Telegram {cid} error: {e}"); ok = False
    return ok

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "prices.json")

def load_latest():
    """Đọc giá mới nhất từ prices.json (đã fetch bởi fetch_prices.py)."""
    try:
        with open(DATA_FILE) as f:
            d = json.load(f)
        l = d.get("latest")
        if not l: return None, None
        gold = {"price": l["price"], "change": l.get("change",0),
                "change_pct": l.get("change_pct",0),
                "high_24h": l.get("high",0), "low_24h": l.get("low",0),
                "source": l.get("source","")}
        sjc = None
        if l.get("sjc_buy",0) > 0:
            sjc = {"buy": l["sjc_buy"], "sell": l["sjc_sell"],
                   "real": l.get("sjc_real", False),
                   "updated": l.get("sjc_updated", "")}
        return gold, sjc
    except Exception as e:
        print(f"  load_latest error: {e}"); return None, None

def build_daily_report():
    gold, sjc = load_latest()
    if not gold:
        # Fallback: fetch live nếu không đọc được file
        gold = fetch_gold_price()
        if not gold or gold["price"] == 0: return "⚠️ Không lấy được giá vàng."
        sjc = get_sjc(gold["price"])

    a = analyze(gold)
    p = gold["price"]; ch = gold.get("change",0); cpct = gold.get("change_pct",0)
    icon = "🟢 ▲" if ch >= 0 else "🔴 ▼"
    now = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M")

    msg = f"""⬙ <b>GOLD SENTINEL</b> — {now}
━━━━━━━━━━━━━━━━━━━━

🪙 <b>XAU/USD:</b> ${p:,.1f} {icon} {abs(ch):.1f} ({cpct:+.1f}%)"""
    if gold.get("high_24h") and gold.get("low_24h"):
        msg += f"\n   H: ${gold['high_24h']:,.1f} | L: ${gold['low_24h']:,.1f}"
    if sjc:
        tag = "✅ giá thật" if sjc.get("real") else "📊 ước tính"
        updated = f" · {sjc['updated']}" if sjc.get("updated") else ""
        msg += f"\n\n🏦 <b>SJC {tag}:</b>{updated}\n   Mua: {sjc['buy']}tr | Bán: {sjc['sell']}tr"
    msg += f"""

━━━━━━━━━━━━━━━━━━━━
📊 Kháng cự: $5,000 | HT: $4,550 / $4,360
   Bear: $4,200 | Từ ATH: -{a['from_ath']:.1f}%
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
<i>⚠️ Không phải tư vấn tài chính.</i>"""
    return msg

def send_fomc_reminder():
    today = datetime.now(VN_TZ)
    for m in FOMC_SCHEDULE:
        md = datetime.strptime(m["date"], "%Y-%m-%d").replace(tzinfo=VN_TZ)
        d = (md-today).days
        if d == 1:
            sep = "📈 DOT PLOT!" if m.get('has_sep') else "📋 Thường"
            send_telegram(f"🚨 <b>FOMC NGÀY MAI!</b>\n📅 {md.strftime('%d/%m/%Y')} {sep}\n⏰ ~2:00 AM VN\n<i>⚠️ Không phải tư vấn tài chính.</i>")
            break
        if d == 7:
            send_telegram(f"📅 <b>FOMC trong 1 tuần</b>\n📆 {md.strftime('%d/%m/%Y')} {'📈 DOT PLOT' if m.get('has_sep') else ''}\n<i>⚠️ Không phải tư vấn tài chính.</i>")
            break
