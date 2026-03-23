"""
GOLD SENTINEL — Price Fetcher v3
- Giá thế giới: gold-api.com (unlimited) + goldapi.io (backup)
- Giá SJC thật: sjc.com.vn/giavang/textContent.php
"""
import os, json, re, requests
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PRICES_FILE = os.path.join(DATA_DIR, "prices.json")
MAX_HISTORY_DAYS = 90
GOLD_API_KEY = os.getenv("GOLD_API_KEY", "")

def fetch_from_gold_api_free():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10)
        if r.status_code != 200: return None
        d = r.json(); p = d.get("price", 0)
        if p == 0: return None
        return {"price": p, "change": d.get("change",0), "change_pct": d.get("changePercentage",0),
                "high": d.get("high",0), "low": d.get("low",0), "source": "gold-api.com"}
    except Exception as e:
        print(f"  gold-api.com error: {e}"); return None

def fetch_from_goldapi_io():
    if not GOLD_API_KEY: return None
    try:
        r = requests.get("https://www.goldapi.io/api/XAU/USD",
                        headers={"x-access-token": GOLD_API_KEY}, timeout=10)
        if r.status_code != 200: return None
        d = r.json(); p = d.get("price", 0)
        if p == 0: return None
        return {"price": p, "change": d.get("ch",0), "change_pct": d.get("chp",0),
                "high": d.get("high_price",0), "low": d.get("low_price",0), "source": "goldapi.io"}
    except Exception as e:
        print(f"  goldapi.io error: {e}"); return None

def fetch_gold_price():
    for fn, name in [(fetch_from_gold_api_free,"gold-api.com"),(fetch_from_goldapi_io,"goldapi.io")]:
        print(f"  Trying {name}...")
        r = fn()
        if r:
            print(f"  ✅ World: ${r['price']:,.1f} ({r['source']})")
            return r
    return None

# ---- SJC Parser ----
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

def parse_price_num(text):
    try:
        num = int(re.sub(r'[^\d]', '', text.strip()))
        if num > 1_000_000: return round(num / 1_000_000, 1)
        elif num > 10_000: return round(num / 1_000, 1)
        elif num > 100: return float(num)
    except: pass
    return 0

def fetch_sjc_real():
    try:
        r = requests.get("https://sjc.com.vn/giavang/textContent.php", timeout=10,
                        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://sjc.com.vn/gia-vang-online"})
        if r.status_code != 200:
            print(f"  SJC status: {r.status_code}"); return None
        text = r.text.strip()
        print(f"  SJC response ({len(text)} chars): {text[:300]}...")

        # Try JSON
        try:
            data = json.loads(text)
            if isinstance(data, list) and data:
                for item in data:
                    name = str(item.get("name","") or item.get("type","")).upper()
                    buy = item.get("buy",0) or item.get("mua",0) or item.get("buy_1l",0) or item.get("buy_price",0)
                    sell = item.get("sell",0) or item.get("ban",0) or item.get("sell_1l",0) or item.get("sell_price",0)
                    b = parse_price_num(str(buy)) if isinstance(buy, str) else (round(buy/1e6,1) if buy > 1e6 else (round(buy/1e3,1) if buy > 1e4 else buy))
                    s = parse_price_num(str(sell)) if isinstance(sell, str) else (round(sell/1e6,1) if sell > 1e6 else (round(sell/1e3,1) if sell > 1e4 else sell))
                    if b > 50 and s > 50:
                        if "1L" in name or "MIẾNG" in name or "MIENG" in name:
                            return {"buy": b, "sell": s, "source": "sjc.com.vn", "real": True}
                # Fallback: first item
                item = data[0]
                buy = item.get("buy",0) or item.get("mua",0) or item.get("buy_1l",0)
                sell = item.get("sell",0) or item.get("ban",0) or item.get("sell_1l",0)
                b = parse_price_num(str(buy)) if isinstance(buy, str) else (round(buy/1e6,1) if buy > 1e6 else buy)
                s = parse_price_num(str(sell)) if isinstance(sell, str) else (round(sell/1e6,1) if sell > 1e6 else sell)
                if b > 50 and s > 50:
                    return {"buy": b, "sell": s, "source": "sjc.com.vn", "real": True}
        except json.JSONDecodeError: pass

        # Try HTML table
        if "<t" in text.lower():
            parser = SJCParser(); parser.feed(text)
            for row in parser.rows:
                row_text = " ".join(row).upper()
                if "SJC" in row_text:
                    nums = [parse_price_num(c) for c in row if parse_price_num(c) > 50]
                    if len(nums) >= 2:
                        return {"buy": nums[0], "sell": nums[1], "source": "sjc.com.vn", "real": True}
            for row in parser.rows:
                nums = [parse_price_num(c) for c in row if parse_price_num(c) > 50]
                if len(nums) >= 2:
                    return {"buy": nums[0], "sell": nums[1], "source": "sjc.com.vn", "real": True}

        # Try regex
        nums = [parse_price_num(p) for p in re.findall(r'[\d,.]+', text)]
        valid = [n for n in nums if 50 < n < 500]
        if len(valid) >= 2:
            return {"buy": valid[0], "sell": valid[1], "source": "sjc.com.vn", "real": True}

        print("  ⚠️ Could not parse SJC response"); return None
    except Exception as e:
        print(f"  SJC error: {e}"); return None

def fetch_sjc_fallback(world_price):
    if not world_price: return None
    w = world_price * 26339 * 37.5 / 31.1035
    return {"buy": round((w+25e6)/1e6,1), "sell": round((w+28e6)/1e6,1), "source": "estimated", "real": False}

def fetch_sjc(world_price=0):
    print("  Fetching SJC from sjc.com.vn...")
    result = fetch_sjc_real()
    if result:
        print(f"  ✅ SJC: Mua {result['buy']}tr / Bán {result['sell']}tr (REAL)")
        return result
    print("  ⚠️ SJC API failed, using estimate...")
    result = fetch_sjc_fallback(world_price)
    if result: print(f"  📊 SJC estimate: Mua {result['buy']}tr / Bán {result['sell']}tr")
    return result

# ---- Main ----
def load_prices():
    if not os.path.exists(PRICES_FILE): return {"history": [], "latest": None}
    try:
        with open(PRICES_FILE) as f: return json.load(f)
    except: return {"history": [], "latest": None}

def save_prices(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PRICES_FILE, "w") as f: json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    vn = timezone(timedelta(hours=7)); now = datetime.now(vn)
    print(f"⬙ Gold Sentinel v3 — {now.strftime('%Y-%m-%d %H:%M')} VN")
    print()
    print("📌 World price:")
    gold = fetch_gold_price()
    if not gold: print("  ❌ Failed!"); return False
    print()
    print("📌 SJC price:")
    sjc = fetch_sjc(gold["price"])
    print()

    data = load_prices()
    rec = {"timestamp": now.isoformat(), "date": now.strftime("%Y-%m-%d"), "hour": now.hour, "minute": now.minute,
           "price": gold["price"], "change": gold["change"], "change_pct": gold["change_pct"],
           "high": gold["high"], "low": gold["low"], "source": gold["source"]}
    if sjc:
        rec["sjc_buy"] = sjc["buy"]; rec["sjc_sell"] = sjc["sell"]
        rec["sjc_source"] = sjc["source"]; rec["sjc_real"] = sjc.get("real", False)
    else:
        rec["sjc_buy"] = 0; rec["sjc_sell"] = 0; rec["sjc_source"] = "unavailable"; rec["sjc_real"] = False

    data["latest"] = rec
    hist = data.get("history", [])
    dup = False
    for h in hist:
        if h.get("date") == rec["date"] and h.get("hour") == rec["hour"]: h.update(rec); dup = True; break
    if not dup: hist.append(rec)
    cutoff = (now - timedelta(days=MAX_HISTORY_DAYS)).isoformat()
    hist = [h for h in hist if h["timestamp"] >= cutoff]
    daily = {}
    for h in hist:
        d = h["date"]
        if d not in daily or h["timestamp"] > daily[d]["timestamp"]: daily[d] = h

    data["history"] = hist; data["daily"] = sorted(daily.values(), key=lambda x: x["date"])
    data["updated_at"] = now.isoformat(); data["total_records"] = len(hist)
    save_prices(data)
    real_tag = "✅ REAL" if sjc and sjc.get("real") else "📊 EST"
    print(f"💾 Saved: {len(hist)} records | ${gold['price']:,.1f} | SJC {sjc['buy'] if sjc else '?'}tr/{sjc['sell'] if sjc else '?'}tr [{real_tag}]")
    return True

if __name__ == "__main__": main()
