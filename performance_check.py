import os
import json
import requests
from datetime import datetime, timedelta
import yfinance as yf

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
MY_CHAT_ID = os.environ.get('MY_CHAT_ID')

def send_telegram(text):
    if not TELEGRAM_TOKEN or not MY_CHAT_ID:
        print("Telegram credentials missing")
        return False
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={
                "chat_id": MY_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            },
            timeout=15
        )
        return res.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def get_current_price(stock_name):
    """Try to fetch current price using yfinance"""
    try:
        # Common Indian stock suffixes
        for suffix in [".NS", ".BO", ""]:
            symbol = stock_name.replace(" ", "") + suffix
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if not hist.empty:
                return round(hist['Close'].iloc[-1], 2)
        return None
    except:
        return None

def calculate_performance():
    log_file = "performance_log.json"
    if not os.path.exists(log_file):
        send_telegram("📊 *Performance Report*\n\nNo recommendations logged yet.")
        return

    with open(log_file, "r") as f:
        log = json.load(f)

    if not log:
        send_telegram("📊 *Performance Report*\n\nNo recommendations logged yet.")
        return

    today = datetime.now().date()
    results = []
    wins = 0
    losses = 0
    neutral = 0
    total_return = 0
    counted = 0

    for entry in log:
        try:
            entry_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
            days_held = (today - entry_date).days
            if days_held < 1:
                continue  # Skip today's entries

            entry_price = float(str(entry["entry_price"]).replace(",", "").replace("₹", ""))
            current_price = get_current_price(entry["name"])

            if current_price is None:
                continue

            pct_change = ((current_price - entry_price) / entry_price) * 100
            total_return += pct_change
            counted += 1

            if pct_change > 5:
                status = "✅ Win"
                wins += 1
            elif pct_change < -5:
                status = "❌ Loss"
                losses += 1
            else:
                status = "➖ Neutral"
                neutral += 1

            results.append({
                "name": entry["name"],
                "days": days_held,
                "entry": entry_price,
                "current": current_price,
                "pct": round(pct_change, 2),
                "status": status,
                "screens": ", ".join(entry.get("screens", []))
            })
        except Exception as e:
            print(f"Error processing {entry.get('name')}: {e}")
            continue

    # Build report
    report = [f"📊 *Weekly Performance Report*\n"]
    report.append(f"📅 {datetime.now().strftime('%d %b %Y')}\n")

    if counted == 0:
        report.append("Not enough data yet (need at least 1 day old recommendations).")
        send_telegram("\n".join(report))
        return

    win_rate = (wins / counted) * 100 if counted > 0 else 0
    avg_return = total_return / counted if counted > 0 else 0

    report.append(f"*Summary*")
    report.append(f"• Total Tracked: {counted}")
    report.append(f"• Wins (>5%): {wins}")
    report.append(f"• Losses (<-5%): {losses}")
    report.append(f"• Neutral: {neutral}")
    report.append(f"• Win Rate: *{win_rate:.1f}%*")
    report.append(f"• Average Return: *{avg_return:.2f}%*\n")

    # Top performers
    results_sorted = sorted(results, key=lambda x: x["pct"], reverse=True)
    report.append("*Top Performers*")
    for r in results_sorted[:5]:
        report.append(f"• {r['name']}: {r['pct']}% ({r['days']}d) {r['status']}")

    report.append("\n*Weakest*")
    for r in results_sorted[-3:]:
        report.append(f"• {r['name']}: {r['pct']}% ({r['days']}d) {r['status']}")

    report.append("\n_System is in 3-month evaluation mode_")

    send_telegram("\n".join(report))
    print("✅ Performance report sent")

if __name__ == "__main__":
    calculate_performance()
