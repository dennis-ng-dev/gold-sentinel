#!/bin/bash
set -e
echo ""
echo "⬙ Gold Sentinel — Update v2: fix API priority + add dashboard"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ ! -d ".git" ]; then
    echo "❌ Chạy trong thư mục gold-sentinel: cd gold-sentinel && bash update2.sh"
    exit 1
fi

GITHUB_USER=$(gh repo view --json owner -q .owner.login)
DATA_URL="https://raw.githubusercontent.com/${GITHUB_USER}/gold-sentinel/main/data/prices.json"
echo "📊 Data URL: $DATA_URL"
echo ""

# ------- Cập nhật gold_sentinel_bot.py — ưu tiên free API -------
cat > gold_sentinel_bot.py << 'PYEOF'
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
PYEOF
echo "  ✅ gold_sentinel_bot.py (v2 — free API first)"

# ------- Tạo dashboard (đọc từ GitHub JSON) -------
mkdir -p docs

cat > docs/index.html << HTMLEOF
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>⬙ Gold Sentinel</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  min-height: 100vh;
  background: linear-gradient(170deg, #0f0e0b, #1a1714 30%, #0f0e0b);
  color: #e8dcc8;
  font-family: 'Crimson Pro', Georgia, serif;
}

.container { max-width: 800px; margin: 0 auto; padding: 24px 16px; }

header { text-align: center; margin-bottom: 28px; }
h1 {
  font-size: 28px; font-weight: 300; letter-spacing: 6px;
  background: linear-gradient(135deg, #f5d77a, #d4a017, #b8860b);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  text-transform: uppercase;
}
.subtitle {
  font-size: 11px; letter-spacing: 4px; color: #8a8070;
  font-family: 'JetBrains Mono', monospace; text-transform: uppercase;
  margin-top: 4px;
}

.action-banner {
  border-radius: 12px; padding: 16px 20px; margin-bottom: 20px;
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 12px;
}
.action-label { font-size: 11px; letter-spacing: 3px; font-family: 'JetBrains Mono', monospace; text-transform: uppercase; margin-bottom: 4px; }
.action-text { font-size: 18px; font-weight: 600; }

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px; }
@media (max-width: 600px) { .grid-2 { grid-template-columns: 1fr; } }

.card {
  background: linear-gradient(145deg, #1e1b16, #252119);
  border: 1px solid rgba(212,160,23,0.2);
  border-radius: 12px; padding: 18px;
}

.card-label {
  font-size: 10px; letter-spacing: 3px; color: #8a8070;
  font-family: 'JetBrains Mono', monospace; text-transform: uppercase;
  margin-bottom: 8px;
}

.price-big {
  font-size: 32px; font-weight: 700; letter-spacing: 1px;
  background: linear-gradient(135deg, #f5d77a, #d4a017);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}

.change { font-size: 13px; font-family: 'JetBrains Mono', monospace; font-weight: 600; margin-top: 6px; }
.change.down { color: #ef4444; }
.change.up { color: #10b981; }

.sjc-prices { display: flex; gap: 16px; align-items: baseline; }
.sjc-prices > div > .label { font-size: 11px; color: #6b6050; }
.sjc-prices > div > .val { font-size: 22px; font-weight: 700; }

.alert-box {
  padding: 10px 14px; border-radius: 8px; font-size: 13px; line-height: 1.6;
  margin-bottom: 8px;
}
.alert-warning { background: #f59e0b12; border: 1px solid #f59e0b30; }
.alert-info { background: #3b82f612; border: 1px solid #3b82f630; }
.alert-danger { background: #ef444415; border: 1px solid #ef444440; }
.alert-success { background: #10b98112; border: 1px solid #10b98130; }

.metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px; }
@media (max-width: 600px) { .metrics { grid-template-columns: repeat(2, 1fr); } }
.metric {
  background: #1e1b16; border: 1px solid rgba(212,160,23,0.1);
  border-radius: 10px; padding: 12px; text-align: center;
}
.metric .label { font-size: 9px; letter-spacing: 2px; color: #6b6050; font-family: monospace; text-transform: uppercase; margin-bottom: 4px; }
.metric .val { font-size: 16px; font-weight: 700; color: #d4a017; font-family: monospace; }
.metric .sub { font-size: 10px; color: #6b6050; margin-top: 2px; }

.chart-container { position: relative; width: 100%; }
canvas { width: 100% !important; height: 200px !important; }

.loading { text-align: center; padding: 40px; color: #8a8070; font-family: monospace; }
.loading .spinner { display: inline-block; width: 20px; height: 20px; border: 2px solid #3a352c; border-top: 2px solid #d4a017; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 12px; }
@keyframes spin { to { transform: rotate(360deg); } }

.fomc-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; border-radius: 8px; margin-bottom: 6px;
  background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.04);
}
.fomc-item.next { background: rgba(212,160,23,0.08); border: 1px solid rgba(212,160,23,0.3); }
.fomc-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.fomc-date { font-family: monospace; font-size: 12px; width: 80px; }
.fomc-badge { font-size: 9px; padding: 2px 6px; border-radius: 3px; font-family: monospace; letter-spacing: 1px; }

.target-bar { margin-bottom: 12px; }
.target-bar .header { display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 12px; }
.target-bar .bar { height: 6px; background: #1a1714; border-radius: 3px; position: relative; overflow: hidden; }
.target-bar .fill { height: 100%; border-radius: 3px; }
.target-bar .marker { position: absolute; top: -2px; width: 2px; height: 10px; background: #d4a017; border-radius: 1px; }

footer { text-align: center; margin-top: 28px; padding-top: 16px; border-top: 1px solid rgba(212,160,23,0.1); }
footer p { font-size: 10px; color: #5a5040; letter-spacing: 2px; font-family: monospace; line-height: 1.8; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>⬙ Gold Sentinel</h1>
    <div class="subtitle" id="updated-at">Đang tải...</div>
  </header>

  <div class="action-banner" id="action-banner">
    <div>
      <div class="action-label" id="action-label">Gợi ý hành động</div>
      <div class="action-text" id="action-text">Đang tải...</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:11px;color:#8a8070;font-family:monospace">FOMC tiếp theo</div>
      <div style="font-size:18px;font-weight:600;color:#d4a017" id="fomc-countdown">--</div>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <div class="card-label">XAU/USD</div>
      <div class="price-big" id="xau-price">--</div>
      <div class="change" id="xau-change">--</div>
    </div>
    <div class="card">
      <div class="card-label">Vàng SJC (ước tính)</div>
      <div class="sjc-prices">
        <div><div class="label">Mua</div><div class="val" id="sjc-buy">--</div></div>
        <div style="color:#3a352c;font-size:20px">|</div>
        <div><div class="label">Bán</div><div class="val" id="sjc-sell">--</div></div>
      </div>
      <div class="change" id="sjc-source" style="color:#6b6050;font-size:11px;margin-top:8px">--</div>
    </div>
  </div>

  <div class="card" style="margin-bottom:20px">
    <div class="card-label">Biểu đồ giá · Daily</div>
    <div class="chart-container">
      <canvas id="price-chart"></canvas>
    </div>
  </div>

  <div class="card" style="margin-bottom:20px">
    <div class="card-label">Cảnh báo</div>
    <div id="alerts-container"><div class="loading"><div class="spinner"></div><br>Đang tải...</div></div>
  </div>

  <div class="metrics" id="metrics">
    <div class="metric"><div class="label">ATH</div><div class="val">\$5,595</div><div class="sub">29/01/2026</div></div>
    <div class="metric"><div class="label">Từ ATH</div><div class="val" id="m-ath">--</div><div class="sub" id="m-ath-usd">--</div></div>
    <div class="metric"><div class="label">Records</div><div class="val" id="m-records">--</div><div class="sub">data points</div></div>
    <div class="metric"><div class="label">Nguồn</div><div class="val" id="m-source">--</div><div class="sub">API</div></div>
  </div>

  <div class="card" style="margin-bottom:20px">
    <div class="card-label">Mục tiêu cuối 2026</div>
    <div id="targets-container"></div>
  </div>

  <footer>
    <p>⚠️ Không phải tư vấn tài chính. Chỉ mang tính tham khảo.<br>Dữ liệu cập nhật mỗi giờ từ GitHub Actions.</p>
  </footer>
</div>

<script>
const DATA_URL = "${DATA_URL}";
const ATH = 5595;
const FOMC = [
  {date:"2026-04-29",sep:false},{date:"2026-06-17",sep:true},
  {date:"2026-07-29",sep:false},{date:"2026-09-16",sep:true},
  {date:"2026-10-28",sep:false},{date:"2026-12-09",sep:true}
];
const TARGETS = [
  {bank:"J.P. Morgan",target:6300,color:"#3b82f6"},
  {bank:"UBS",target:6200,color:"#8b5cf6"},
  {bank:"Deutsche Bank",target:6000,color:"#10b981"},
  {bank:"Goldman Sachs",target:5400,color:"#f59e0b"},
  {bank:"Scotiabank",target:4100,color:"#6b7280"},
];
const LEVELS = {resistance:5000, support1:4550, support2:4360, bear:4200};

function analyze(p) {
  let act,emoji,color,alerts=[];
  if(p<=LEVELS.bear){act="CHỜ — Dưới 200-EMA";emoji="🔴";color="#ef4444";alerts.push({t:"danger",m:"⚠️ DƯỚI 200-EMA — Bear Market!"});}
  else if(p<=LEVELS.support2){act="QUAN SÁT — Chờ đảo chiều";emoji="🟠";color="#f97316";alerts.push({t:"warning",m:"🟡 Hỗ trợ $4,360"});}
  else if(p<=LEVELS.support1){act="CÂN NHẮC — DCA 20-30%";emoji="🟡";color="#f59e0b";alerts.push({t:"warning",m:"🟡 Hỗ trợ $4,550 bị test"});}
  else if(p<LEVELS.resistance){act="MUA DCA — Chia nhỏ đợt";emoji="🔵";color="#3b82f6";alerts.push({t:"info",m:"📊 Dưới $5,000 — Tích lũy"});}
  else{act="GIỮ — Uptrend OK";emoji="🟢";color="#10b981";alerts.push({t:"success",m:"✅ Trên $5,000"});}
  let nf=null,df=null,now=new Date();
  for(let f of FOMC){let d=new Date(f.date);if(d>now){nf=f;df=Math.ceil((d-now)/864e5);
    if(df<=7)alerts.push({t:"warning",m:"⏰ FOMC trong "+df+" ngày!"});
    else if(df<=14)alerts.push({t:"info",m:"📅 FOMC sắp họp ("+df+"d)"});break;}}
  let uj=((6300-p)/p*100).toFixed(1), ug=((5400-p)/p*100).toFixed(1);
  alerts.push({t:"info",m:"📈 Upside: JPM +"+uj+"% | GS +"+ug+"%"});
  return {act,emoji,color,alerts,df};
}

async function load(){
  try{
    const r=await fetch(DATA_URL+"?t="+Date.now());
    if(!r.ok) throw new Error("Fetch failed");
    const d=await r.json();
    if(!d.latest) throw new Error("No data");
    render(d);
  }catch(e){
    document.getElementById("action-text").textContent="❌ Lỗi tải dữ liệu: "+e.message;
  }
}

function render(d){
  const l=d.latest, p=l.price;
  // Updated at
  const ua=new Date(d.updated_at);
  document.getElementById("updated-at").textContent=
    "Cập nhật: "+ua.toLocaleString("vi-VN")+" · "+l.source;

  // Prices
  document.getElementById("xau-price").textContent="$"+p.toLocaleString("en",{minimumFractionDigits:1});
  const ch=l.change||0, cpct=l.change_pct||0;
  const chEl=document.getElementById("xau-change");
  chEl.textContent=(ch>=0?"▲ ":"▼ ")+Math.abs(ch).toFixed(1)+" ("+cpct.toFixed(1)+"%)";
  chEl.className="change "+(ch>=0?"up":"down");

  document.getElementById("sjc-buy").textContent=l.sjc_buy+"tr";
  document.getElementById("sjc-sell").textContent=l.sjc_sell+"tr";
  document.getElementById("sjc-source").textContent="Premium ~28tr vs thế giới · "+l.source;

  // Analysis
  const a=analyze(p);
  const ab=document.getElementById("action-banner");
  ab.style.background="linear-gradient(135deg,"+a.color+"15,"+a.color+"08)";
  ab.style.border="1px solid "+a.color+"40";
  document.getElementById("action-label").style.color=a.color;
  document.getElementById("action-text").style.color=a.color;
  document.getElementById("action-text").textContent=a.emoji+" "+a.act;
  document.getElementById("fomc-countdown").textContent=a.df?a.df+"d":"--";

  // Alerts
  const ac=document.getElementById("alerts-container"); ac.innerHTML="";
  a.alerts.forEach(al=>{
    const cls={danger:"alert-danger",warning:"alert-warning",info:"alert-info",success:"alert-success"};
    ac.innerHTML+='<div class="alert-box '+(cls[al.t]||"alert-info")+'">'+al.m+'</div>';
  });

  // Metrics
  const fromAth=((ATH-p)/ATH*100).toFixed(1);
  document.getElementById("m-ath").textContent="-"+fromAth+"%";
  document.getElementById("m-ath-usd").textContent="-$"+(ATH-p).toFixed(0);
  document.getElementById("m-records").textContent=d.total_records||"--";
  document.getElementById("m-source").textContent=l.source.split(".")[0];

  // Targets
  const tc=document.getElementById("targets-container"); tc.innerHTML="";
  const mx=7000;
  TARGETS.forEach(t=>{
    const pct=((t.target-p)/p*100).toFixed(1);
    const bw=(t.target/mx*100);
    const cw=(p/mx*100);
    tc.innerHTML+=
      '<div class="target-bar"><div class="header"><span>'+t.bank+'</span>'+
      '<span style="font-family:monospace;color:'+t.color+';font-weight:700">$'+t.target.toLocaleString()+' ('+(pct>0?'+':'')+pct+'%)</span></div>'+
      '<div class="bar"><div class="fill" style="width:'+bw+'%;background:linear-gradient(90deg,'+t.color+'40,'+t.color+'80)"></div>'+
      '<div class="marker" style="left:'+cw+'%"></div></div></div>';
  });

  // Chart
  drawChart(d.daily||[]);
}

function drawChart(daily){
  const canvas=document.getElementById("price-chart");
  const ctx=canvas.getContext("2d");
  const dpr=window.devicePixelRatio||1;
  const rect=canvas.parentElement.getBoundingClientRect();
  canvas.width=rect.width*dpr; canvas.height=200*dpr;
  canvas.style.width=rect.width+"px"; canvas.style.height="200px";
  ctx.scale(dpr,dpr);
  const W=rect.width, H=200;

  if(daily.length<2){ctx.fillStyle="#8a8070";ctx.font="12px monospace";ctx.fillText("Chưa đủ dữ liệu...",W/2-50,H/2);return;}

  const prices=daily.map(d=>d.price);
  const mn=Math.min(...prices)-100, mx=Math.max(...prices)+100, rng=mx-mn;
  const toX=i=>(i/(daily.length-1))*W;
  const toY=p=>H-((p-mn)/rng)*H;

  // Support/resistance lines
  [{v:5000,c:"#10b981",l:"$5,000"},{v:4550,c:"#f59e0b",l:"$4,550"},{v:4360,c:"#f97316",l:"$4,360"},{v:4200,c:"#ef4444",l:"200-EMA"}]
  .forEach(lv=>{
    const y=toY(lv.v);
    if(y<0||y>H)return;
    ctx.strokeStyle=lv.c; ctx.globalAlpha=0.3; ctx.setLineDash([6,4]); ctx.lineWidth=1;
    ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke();
    ctx.setLineDash([]); ctx.globalAlpha=0.6;
    ctx.fillStyle=lv.c; ctx.font="10px monospace"; ctx.textAlign="right";
    ctx.fillText(lv.l,W-4,y-4); ctx.globalAlpha=1;
  });

  // Area
  ctx.beginPath(); ctx.moveTo(toX(0),toY(prices[0]));
  for(let i=1;i<prices.length;i++) ctx.lineTo(toX(i),toY(prices[i]));
  ctx.lineTo(W,H); ctx.lineTo(0,H); ctx.closePath();
  const grad=ctx.createLinearGradient(0,0,0,H);
  grad.addColorStop(0,"rgba(212,160,23,0.25)"); grad.addColorStop(1,"rgba(212,160,23,0.02)");
  ctx.fillStyle=grad; ctx.fill();

  // Line
  ctx.beginPath(); ctx.moveTo(toX(0),toY(prices[0]));
  for(let i=1;i<prices.length;i++) ctx.lineTo(toX(i),toY(prices[i]));
  ctx.strokeStyle="#d4a017"; ctx.lineWidth=2.5; ctx.lineJoin="round"; ctx.stroke();

  // Current dot
  const lx=toX(prices.length-1), ly=toY(prices[prices.length-1]);
  ctx.beginPath(); ctx.arc(lx,ly,5,0,Math.PI*2);
  ctx.fillStyle="#d4a017"; ctx.fill();
  ctx.strokeStyle="#1a1714"; ctx.lineWidth=2; ctx.stroke();

  // Date labels
  ctx.fillStyle="#8a8070"; ctx.font="9px monospace"; ctx.textAlign="center";
  const step=Math.max(1,Math.floor(daily.length/6));
  for(let i=0;i<daily.length;i+=step){
    const dt=daily[i].date.slice(5); // MM-DD
    ctx.fillText(dt.replace("-","/"),toX(i),H-4);
  }
}

load();
setInterval(load, 5*60*1000); // Refresh mỗi 5 phút
</script>
</body>
</html>
HTMLEOF
echo "  ✅ docs/index.html (dashboard)"

# ------- Commit & push -------
echo ""
echo "🚀 Pushing..."
git add -A
git commit -m "✨ v2: free API priority + web dashboard"
git push

# ------- Enable GitHub Pages -------
echo ""
echo "🌐 Bật GitHub Pages..."
gh repo edit --enable-wiki=false 2>/dev/null || true
gh api -X POST "repos/${GITHUB_USER}/gold-sentinel/pages" \
  -f source='{"branch":"main","path":"/docs"}' 2>/dev/null || \
gh api -X PUT "repos/${GITHUB_USER}/gold-sentinel/pages" \
  -f source='{"branch":"main","path":"/docs"}' 2>/dev/null || \
echo "   ⚠️ Bật Pages thủ công: Settings → Pages → Source: main /docs"

PAGES_URL="https://${GITHUB_USER}.github.io/gold-sentinel/"

echo ""
echo "⬙ ════════════════════════════════════════════"
echo "  ✅ HOÀN TẤT!"
echo "  ════════════════════════════════════════════"
echo ""
echo "  📊 Dashboard: $PAGES_URL"
echo "     (Có thể cần 2-3 phút để GitHub Pages active)"
echo ""
echo "  📱 Telegram: gửi 8h sáng + 8h tối VN"
echo "  🪙 Giá cập nhật: mỗi giờ (T2-T6)"
echo "  💾 Data: $DATA_URL"
echo ""
echo "  🔧 Test: gh workflow run gold-sentinel.yml -f send_telegram=true"
echo ""
