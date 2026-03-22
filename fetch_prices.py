"""
GOLD SENTINEL — Price Fetcher
Fetch giá vàng từ nhiều nguồn miễn phí, lưu vào data/prices.json
"""
import os, json, requests
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PRICES_FILE = os.path.join(DATA_DIR, "prices.json")
MAX_HISTORY_DAYS = 90
GOLD_API_KEY = os.getenv("GOLD_API_KEY", "")
USD_VND_RATE = 26339
SJC_PREMIUM = 28_000_000

def fetch_from_gold_api_free():
    try:
        resp = requests.get("https://api.gold-api.com/price/XAU", timeout=10)
        if resp.status_code != 200: return None
        d = resp.json()
        p = d.get("price", 0)
        if p == 0: return None
        return {"price": p, "change": d.get("change",0), "change_pct": d.get("changePercentage",0),
                "high": d.get("high",0), "low": d.get("low",0), "source": "gold-api.com"}
    except Exception as e:
        print(f"  gold-api.com error: {e}"); return None

def fetch_from_goldapi_io():
    if not GOLD_API_KEY: return None
    try:
        resp = requests.get("https://www.goldapi.io/api/XAU/USD",
                          headers={"x-access-token": GOLD_API_KEY}, timeout=10)
        if resp.status_code != 200: return None
        d = resp.json()
        p = d.get("price", 0)
        if p == 0: return None
        return {"price": p, "change": d.get("ch",0), "change_pct": d.get("chp",0),
                "high": d.get("high_price",0), "low": d.get("low_price",0), "source": "goldapi.io"}
    except Exception as e:
        print(f"  goldapi.io error: {e}"); return None

def fetch_gold_price():
    for fn, name in [(fetch_from_gold_api_free, "gold-api.com"), (fetch_from_goldapi_io, "goldapi.io")]:
        print(f"  Trying {name}...")
        r = fn()
        if r: return r
    return None

def calc_sjc(p):
    w = p * USD_VND_RATE * 37.5 / 31.1035
    return {"buy": round((w + SJC_PREMIUM - 3e6) / 1e6, 1), "sell": round((w + SJC_PREMIUM) / 1e6, 1)}

def load_prices():
    if not os.path.exists(PRICES_FILE): return {"history": [], "latest": None}
    try:
        with open(PRICES_FILE) as f: return json.load(f)
    except: return {"history": [], "latest": None}

def save_prices(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PRICES_FILE, "w") as f: json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    vn = timezone(timedelta(hours=7))
    now = datetime.now(vn)
    print(f"⬙ Price Fetch — {now.strftime('%Y-%m-%d %H:%M')} VN")

    gold = fetch_gold_price()
    if not gold: print("  ❌ Fetch failed!"); return False
    print(f"  ✅ ${gold['price']:,.1f} ({gold['source']})")

    sjc = calc_sjc(gold["price"])
    data = load_prices()

    rec = {"timestamp": now.isoformat(), "date": now.strftime("%Y-%m-%d"), "hour": now.hour,
           "price": gold["price"], "change": gold["change"], "change_pct": gold["change_pct"],
           "high": gold["high"], "low": gold["low"],
           "sjc_buy": sjc["buy"], "sjc_sell": sjc["sell"], "source": gold["source"]}

    data["latest"] = rec
    hist = data.get("history", [])

    dup = False
    for h in hist:
        if h.get("date") == rec["date"] and h.get("hour") == rec["hour"]:
            h.update(rec); dup = True; break
    if not dup: hist.append(rec)

    cutoff = (now - timedelta(days=MAX_HISTORY_DAYS)).isoformat()
    hist = [h for h in hist if h["timestamp"] >= cutoff]

    daily = {}
    for h in hist:
        d = h["date"]
        if d not in daily or h["timestamp"] > daily[d]["timestamp"]: daily[d] = h

    data["history"] = hist
    data["daily"] = sorted(daily.values(), key=lambda x: x["date"])
    data["updated_at"] = now.isoformat()
    data["total_records"] = len(hist)

    save_prices(data)
    print(f"  💾 Saved ({len(hist)} records, {len(data['daily'])} days)")
    return True

if __name__ == "__main__": main()
