"""
GOLD SENTINEL — Price Fetcher v3
- Giá thế giới: gold-api.com (unlimited) + goldapi.io (backup)
- Giá SJC thật: sjc.com.vn/GoldPrice/Services/PriceService.ashx
"""
import os, json, re, requests
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PRICES_FILE = os.path.join(DATA_DIR, "prices.json")
MAX_HISTORY_DAYS = 90
DAILY_HISTORY_DAYS = 30
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

# ---- Historical daily from stooq ----
def fetch_daily_history():
    try:
        r = requests.get("https://stooq.com/q/d/l/?s=xauusd&i=d", timeout=15,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            print(f"  stooq status: {r.status_code}"); return []
        lines = r.text.strip().splitlines()
        # CSV: Date,Open,High,Low,Close
        cutoff = (datetime.now(timezone(timedelta(hours=7))) - timedelta(days=DAILY_HISTORY_DAYS)).strftime("%Y-%m-%d")
        result = []
        for line in lines[1:]:  # skip header
            parts = line.split(",")
            if len(parts) < 5: continue
            date, close = parts[0], parts[4]
            if date < cutoff: continue
            try:
                result.append({"date": date, "price": float(close), "source": "stooq"})
            except ValueError:
                continue
        print(f"  ✅ stooq: {len(result)} daily records (last {DAILY_HISTORY_DAYS}d)")
        return sorted(result, key=lambda x: x["date"])
    except Exception as e:
        print(f"  stooq error: {e}"); return []

# ---- SJC ----
def fetch_sjc_real():
    try:
        r = requests.post(
            "https://sjc.com.vn/GoldPrice/Services/PriceService.ashx",
            data={"method": "GetCurrentGoldPricesByBranch", "BranchId": "1"},
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://sjc.com.vn/gia-vang-online"},
            timeout=10
        )
        if r.status_code != 200:
            print(f"  SJC status: {r.status_code}"); return None
        d = r.json()
        if not d.get("success") or not d.get("data"):
            print("  SJC: empty response"); return None
        for item in d["data"]:
            name = item.get("TypeName", "").upper()
            if "1L" in name or "10L" in name or "1KG" in name:
                buy = round(item["BuyValue"] / 1e6, 1)
                sell = round(item["SellValue"] / 1e6, 1)
                if buy > 50 and sell > 50:
                    return {"buy": buy, "sell": sell, "source": "sjc.com.vn", "real": True,
                            "updated": d.get("latestDate", "")}
        print("  SJC: no matching gold type"); return None
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
        print(f"  ✅ SJC: Mua {result['buy']}tr / Bán {result['sell']}tr (REAL, {result.get('updated','')})")
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

def snap_to_slot(dt):
    """Snap thời gian về mốc :00 hoặc :30 gần nhất."""
    snapped_min = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    snapped_hour = dt.hour if snapped_min != 0 or dt.minute < 45 else (dt.hour + 1) % 24
    return dt.replace(minute=snapped_min, second=0, microsecond=0,
                      hour=snapped_hour)

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
    print("📌 Daily history:")
    daily_hist = fetch_daily_history()
    print()

    # Snap timestamp về mốc :00 hoặc :30
    snapped = snap_to_slot(now)
    slot_key = snapped.strftime("%Y-%m-%dT%H:%M")

    data = load_prices()
    rec = {"timestamp": snapped.isoformat(), "slot": slot_key,
           "date": snapped.strftime("%Y-%m-%d"), "hour": snapped.hour, "minute": snapped.minute,
           "price": gold["price"], "change": gold["change"], "change_pct": gold["change_pct"],
           "high": gold["high"], "low": gold["low"], "source": gold["source"]}
    if sjc:
        rec["sjc_buy"] = sjc["buy"]; rec["sjc_sell"] = sjc["sell"]
        rec["sjc_source"] = sjc["source"]; rec["sjc_real"] = sjc.get("real", False)
        rec["sjc_updated"] = sjc.get("updated", "")
    else:
        rec["sjc_buy"] = 0; rec["sjc_sell"] = 0; rec["sjc_source"] = "unavailable"
        rec["sjc_real"] = False; rec["sjc_updated"] = ""

    data["latest"] = rec
    hist = data.get("history", [])
    # Dedup theo slot :00/:30 — giữ record mới nhất trong slot
    hist = [h for h in hist if h.get("slot") != slot_key]
    hist.append(rec)
    cutoff = (now - timedelta(days=MAX_HISTORY_DAYS)).isoformat()
    hist = [h for h in hist if h["timestamp"] >= cutoff]
    hist.sort(key=lambda x: x["timestamp"])

    # Merge daily_hist với history (history ưu tiên cho cùng ngày)
    merged_daily = {r["date"]: r for r in daily_hist}
    for h in hist:
        d = h["date"]
        if d not in merged_daily or h["timestamp"] > merged_daily[d].get("timestamp",""):
            merged_daily[d] = h
    daily_sorted = sorted(merged_daily.values(), key=lambda x: x["date"])

    data["history"] = hist
    data["daily"] = daily_sorted
    data["updated_at"] = now.isoformat(); data["total_records"] = len(hist)
    save_prices(data)
    real_tag = "✅ REAL" if sjc and sjc.get("real") else "📊 EST"
    print(f"💾 Saved: {len(hist)} intraday | {len(daily_sorted)} daily | ${gold['price']:,.1f} | SJC {sjc['buy'] if sjc else '?'}tr/{sjc['sell'] if sjc else '?'}tr [{real_tag}]")
    return True

if __name__ == "__main__": main()
