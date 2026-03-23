"""Runner script cho GitHub Actions."""
from gold_sentinel_bot import build_daily_report, send_telegram, send_fomc_reminder

def main():
    print("📤 Gửi báo cáo hàng ngày...")
    msg = build_daily_report(with_ai=True)
    success = send_telegram(msg)
    if success:
        print("✅ Báo cáo đã gửi!")
    else:
        print("❌ Gửi báo cáo thất bại")

    print("📅 Kiểm tra nhắc nhở FOMC...")
    send_fomc_reminder()
    print("🏁 Done!")

if __name__ == "__main__":
    main()
