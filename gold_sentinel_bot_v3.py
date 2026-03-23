"""
GOLD SENTINEL — Telegram Bot v3
- Giá SJC thật từ sjc.com.vn
- Free API first cho giá thế giới
"""
import os, json, requests, re
from datetime import datetime, timedelta
from html.parser import HTMLParser

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
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
class SJCParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_td = False; self.current_row = []; self.rows = []; self.current_data = ""
    def handle_starttag(self, tag, attrs):
        if tag == "td": self.in_td = True; self.current_data = ""
    def handle_endtag(self, tag):
        if tag == "td": self.in_td = False; self.current_row.append(self.current_data.strip())
        elif tag == "tr":
            if self.current_row: self.rows.append(self.current_row)
            self.current_row = []
    def handle_data(self, data):
        if self.in_td: self.current_data += data

def parse_p(text):
    try:
        num = int(re.sub(r'[^\d]', '', text.strip()))
        if num > 1e6: return round(num/1e6, 1)
        elif num > 1e4: return round(num/1e3, 1)
        elif num > 100: return float(num)
    except: pass
    return 0

def fetch_sjc():
    try:
        r = requests.get("https://sjc.com.vn/giavang/textContent.php", timeout=10,
                        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://sjc.com.vn/gia-vang-online"})
        if r.status_code != 200: return None
        text = r.text.strip()
        # JSON
        try:
            data = json.loads(text)
            if isinstance(data, list) and data:
                item = data[0]
                buy = item.get("buy",0) or item.get("mua",0) or item.get("buy_1l",0)
                sell = item.get("sell",0) or item.get("ban",0) or item.get("sell_1l",0)
                b = round(buy/1e6,1) if buy > 1e6 else (round(buy/1e3,1) if buy > 1e4 else buy)
                s = round(sell/1e6,1) if sell > 1e6 else (round(sell/1e3,1) if sell > 1e4 else sell)
                if b > 50 and s > 50: return {"buy": b, "sell": s, "real": True}
        except: pass
        # HTML
        if "<t" in text.lower():
            parser = SJCParser(); parser.feed(text)
            for row in parser.rows:
                if "SJC" in " ".join(row).upper():
                    nums = [parse_p(c) for c in row if parse_p(c) > 50]
                    if len(nums) >= 2: return {"buy": nums[0], "sell": nums[1], "real": True}
            for row in parser.rows:
                nums = [parse_p(c) for c in row if parse_p(c) > 50]
                if len(nums) >= 2: return {"buy": nums[0], "sell": nums[1], "real": True}
        # Regex
        valid = [parse_p(p) for p in re.findall(r'[\d,.]+', text) if 50 < parse_p(p) < 500]
        if len(valid) >= 2: return {"buy": valid[0], "sell": valid[1], "real": True}
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
    if p <= PRICE_LEVELS["bear_line_200ema"]:
        act="CHỜ — Dưới 200-EMA, rủi ro bear market"; emoji="🔴"; alerts.append("⚠️ DƯỚI 200-EMA ($4,200)!")
    elif p <= PRICE_LEVELS["support_4360"]:
        act="QUAN SÁT — Vùng hỗ trợ mạnh, chờ đảo chiều"; emoji="🟠"; alerts.append("🟡 Hỗ trợ $4,360")
    elif p <= PRICE_LEVELS["support_4550"]:
        act="CÂN NHẮC — Mua DCA đợt 1 (20-30% vốn)"; emoji="🟡"; alerts.append("🟡 Hỗ trợ $4,550 bị test")
    elif p < PRICE_LEVELS["resistance_5000"]:
        act="MUA DCA — Chia nhỏ nhiều đợt"; emoji="🔵"; alerts.append("📊 Dưới $5,000 — Tích lũy")
    else:
        act="GIỮ — Uptrend xác nhận"; emoji="🟢"; alerts.append("✅ Trên $5,000")
    if abs(cpct) > ALERT_THRESHOLD_PCT:
        alerts.append(f"🔥 BẤT THƯỜNG: {'tăng' if cpct>0 else 'giảm'} {abs(cpct):.1f}%!")
    today = datetime.now(); nf = None; dtf = None
    for m in FOMC_SCHEDULE:
        md = datetime.strptime(m["date"], "%Y-%m-%d")
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
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                         json={"chat_id":TELEGRAM_CHAT_ID,"text":msg,"parse_mode":parse_mode,"disable_web_page_preview":True}, timeout=10)
        ok = r.status_code == 200
        print(f"[{datetime.now()}] Telegram {'OK' if ok else 'FAIL: '+r.text}")
        return ok
    except Exception as e:
        print(f"[{datetime.now()}] Telegram error: {e}"); return False

def build_daily_report():
    gold = fetch_gold_price()
    if not gold or gold["price"] == 0: return "⚠️ Không lấy được giá vàng."
    sjc = get_sjc(gold["price"]); a = analyze(gold)
    p = gold["price"]; ch = gold.get("change",0); cpct = gold.get("change_pct",0)
    icon = "🟢 ▲" if ch >= 0 else "🔴 ▼"
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    msg = f"""⬙ <b>GOLD SENTINEL</b> — {now}
━━━━━━━━━━━━━━━━━━━━

🪙 <b>XAU/USD:</b> ${p:,.1f} {icon} {abs(ch):.1f} ({cpct:+.1f}%)"""
    if gold.get("high_24h") and gold.get("low_24h"):
        msg += f"\n   H: ${gold['high_24h']:,.1f} | L: ${gold['low_24h']:,.1f}"
    if sjc:
        tag = "✅" if sjc.get("real") else "📊 ước tính"
        msg += f"\n\n🏦 <b>SJC {tag}:</b>\n   Mua: {sjc['buy']}tr | Bán: {sjc['sell']}tr"
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
    today = datetime.now()
    for m in FOMC_SCHEDULE:
        md = datetime.strptime(m["date"], "%Y-%m-%d"); d = (md-today).days
        if d == 1:
            sep = "📈 DOT PLOT!" if m.get('has_sep') else "📋 Thường"
            send_telegram(f"🚨 <b>FOMC NGÀY MAI!</b>\n📅 {md.strftime('%d/%m/%Y')} {sep}\n⏰ ~2:00 AM VN\n<i>⚠️ Không phải tư vấn tài chính.</i>")
            break
        if d == 7:
            send_telegram(f"📅 <b>FOMC trong 1 tuần</b>\n📆 {md.strftime('%d/%m/%Y')} {'📈 DOT PLOT' if m.get('has_sep') else ''}\n<i>⚠️ Không phải tư vấn tài chính.</i>")
            break
