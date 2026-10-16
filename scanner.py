import os
import json
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime

def get_secret(key):
    return os.environ.get(key)

TELEGRAM_TOKEN = get_secret('TELEGRAM_TOKEN')
MY_CHAT_ID = get_secret('MY_CHAT_ID')
SCREENER_USERNAME = get_secret('SCREENER_USERNAME')
SCREENER_PASSWORD = get_secret('SCREENER_PASSWORD')

if not all([SCREENER_USERNAME, SCREENER_PASSWORD]):
    print("❌ Critical Screener secrets missing")
    exit(1)

# ========== 10 SCREENS ==========
SCREENER_URLS = {
    "High Piotroski": "https://www.screener.in/screens/4000817/high-piotroski-score/",
    "Magic Formula": "https://www.screener.in/screens/4000836/magic-formula-greenblatt/",
    "Darvas Scan": "https://www.screener.in/screens/4000848/darvas-scan/",
    "Jim Slater Zulu": "https://www.screener.in/screens/4003190/jim-slater-zulu/",
    "Driehaus Momentum": "https://www.screener.in/screens/4004103/richard-driehaus-momentum-screen/",
    "Altman Z Score": "https://www.screener.in/screens/4005994/altman-z-score/",
    "Crash Recovery": "https://www.screener.in/screens/4009908/crash-recovery-screener/",
    "Quality 40-80": "https://www.screener.in/screens/2062976/penny-stocks/",
    "Swing Pick": "https://www.screener.in/screens/4026023/swing-pick/",
    "High FII + Promoter": "https://www.screener.in/screens/4033828/high-fii-promoter/"
}

def get_screener_session():
    session = requests.Session()
    login_url = "https://www.screener.in/login/"
    try:
        init_res = session.get(login_url, timeout=15)
        soup = BeautifulSoup(init_res.text, 'html.parser')
        csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        if not csrf:
            print("❌ CSRF token not found")
            return None
        payload = {
            'username': SCREENER_USERNAME,
            'password': SCREENER_PASSWORD,
            'csrfmiddlewaretoken': csrf['value']
        }
        res = session.post(login_url, data=payload, headers={'Referer': login_url}, timeout=15)
        if "logout" in res.text.lower() or res.status_code == 200:
            print("✅ Screener login successful")
            return session
        print("❌ Screener login failed")
        return None
    except Exception as e:
        print(f"⚠️ Login error: {e}")
        return None

def scan_screens(session):
    all_stocks = {}
    screen_counts = {}

    for name, url in SCREENER_URLS.items():
        print(f"🔍 Scanning: {name}")
        try:
            res = session.get(url, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            count = 0
            for row in soup.select("table.data-table tbody tr"):
                link = row.select_one("td a")
                if link and '/company/' in link.get('href', ''):
                    stock = link.text.strip()
                    cols = row.find_all('td')
                    price = cols[2].text.strip().replace(',', '') if len(cols) > 2 else "N/A"

                    if stock not in all_stocks:
                        all_stocks[stock] = {
                            "name": stock,
                            "price": price,
                            "url": "https://www.screener.in" + link['href'],
                            "screens": []
                        }
                    if name not in all_stocks[stock]["screens"]:
                        all_stocks[stock]["screens"].append(name)
                    count += 1
            screen_counts[name] = count
            print(f"   → {count} stocks")
        except Exception as e:
            print(f"⚠️ Error on {name}: {e}")
            screen_counts[name] = 0

    print(f"✅ Total unique stocks: {len(all_stocks)}")
    return all_stocks, screen_counts

def get_news(stock_name):
    try:
        query = stock_name.replace(" ", "+")
        url = f"https://news.google.com/rss/search?q={query}+stock+OR+shares&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(url)
        positive = ['order', 'win', 'bag', 'contract', 'profit', 'rise', 'surge', 'growth', 'expand', 'beat', 'acquire']
        negative = ['loss', 'fall', 'drop', 'decline', 'fraud', 'probe', 'penalty']
        items = []
        sentiment = "Neutral"
        for entry in feed.entries[:3]:
            title = entry.title
            lower = title.lower()
            if any(w in lower for w in positive):
                sentiment = "Positive"
                items.append(f"🟢 {title[:85]}")
            elif any(w in lower for w in negative):
                sentiment = "Negative"
                items.append(f"🔴 {title[:85]}")
            else:
                items.append(f"⚪ {title[:85]}")
        return sentiment, items[:2]
    except:
        return "Neutral", []

def send_telegram(text):
    if not TELEGRAM_TOKEN or not MY_CHAT_ID:
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

def calculate_score(screens, sentiment):
    """Weighted score out of 10"""
    score = 0.0
    screens_set = set(screens)

    # High quality fundamental / institutional
    if "High FII + Promoter" in screens_set:
        score += 2.0
    if "High Piotroski" in screens_set or "Magic Formula" in screens_set:
        score += 2.0

    # Technical / Momentum
    if "Crash Recovery" in screens_set:
        score += 1.5
    if "Swing Pick" in screens_set:
        score += 1.5

    # Multi-screen bonus
    if len(screens_set) >= 3:
        score += 1.0

    # News sentiment
    if sentiment == "Positive":
        score += 1.0

    # Extra quality
    if "Altman Z Score" in screens_set or "Quality 40-80" in screens_set:
        score += 0.5

    # Cap at 10
    return min(round(score, 1), 10.0)

def log_performance(stock_name, price, screens, tags, score, priority):
    """Log all stocks (including low score) for backend monitoring"""
    log_file = "performance_log.json"
    try:
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                log = json.load(f)
        else:
            log = []

        today = datetime.now().strftime("%Y-%m-%d")
        # Update if already logged today, else add new
        updated = False
        for entry in log:
            if entry.get("name") == stock_name and entry.get("date") == today:
                entry["score"] = score
                entry["priority"] = priority
                entry["screens"] = screens
                entry["tags"] = tags
                entry["entry_price"] = price
                updated = True
                break

        if not updated:
            entry = {
                "name": stock_name,
                "date": today,
                "entry_price": price,
                "screens": screens,
                "tags": tags,
                "score": score,
                "priority": priority,
                "logged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            log.append(entry)

        with open(log_file, "w") as f:
            json.dump(log, f, indent=2)
        print(f"📝 Logged: {stock_name} | Score: {score} | Priority: {priority}")
    except Exception as e:
        print(f"⚠️ Performance log error: {e}")

def main():
    print("🔄 Starting Weighted Scoring Scanner...")

    heartbeat = (
        "❤️ *Guru Screener Bot*\n\n"
        f"✅ Running at `{datetime.now().strftime('%Y-%m-%d %H:%M')}`\n"
        "📊 10 Screens Active + Weighted Scoring\n\n"
        "🎯 Priority System:\n"
        "• Score ≥ 6.0 → High Priority\n"
        "• Score 4.0–5.9 → Medium Priority\n"
        "• Score < 4.0 → Backend monitoring only\n\n"
        "📈 Full list → Streamlit Dashboard"
    )
    send_telegram(heartbeat)

    session = get_screener_session()
    if not session:
        send_telegram("❌ Screener login failed. Check secrets.")
        return

    stocks, counts = scan_screens(session)

    if not stocks:
        send_telegram("⚠️ No stocks found today.")
        return

    # Process all stocks with scoring
    scored_stocks = []
    for name, data in stocks.items():
        sentiment, news = get_news(name)
        score = calculate_score(data["screens"], sentiment)

        if score >= 6.0:
            priority = "High"
        elif score >= 4.0:
            priority = "Medium"
        else:
            priority = "Low"

        tags = []
        if "Crash Recovery" in data["screens"]:
            tags.append("🚀 Recovery")
        if "Swing Pick" in data["screens"]:
            tags.append("📈 Swing")
        if "High FII + Promoter" in data["screens"]:
            tags.append("🏛 High FII + Promoter")
        if "Quality 40-80" in data["screens"]:
            tags.append("💎 40-80")
        if len(data["screens"]) >= 3:
            tags.append("🔥 Multi-Screen")
        if sentiment == "Positive":
            tags.append("📰 News+")
        elif sentiment == "Negative":
            tags.append("⚠️ News-")

        scored_stocks.append({
            "name": name,
            "price": data["price"],
            "url": data["url"],
            "screens": data["screens"],
            "screens_str": ", ".join(data["screens"]),
            "score": score,
            "priority": priority,
            "tags": tags,
            "sentiment": sentiment,
            "news": news
        })

        # Log everything (including Low priority) for backend monitoring
        log_performance(name, data["price"], data["screens"], tags, score, priority)

    # Sort by score descending
    scored_stocks = sorted(scored_stocks, key=lambda x: x["score"], reverse=True)

    # Save for Streamlit
    results = {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_stocks": len(stocks),
        "screen_counts": counts,
        "stocks": [
            {
                "name": s["name"],
                "price": s["price"],
                "screens": s["screens_str"],
                "screen_count": len(s["screens"]),
                "score": s["score"],
                "priority": s["priority"],
                "url": s["url"]
            } for s in scored_stocks
        ]
    }
    with open("scan_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("✅ scan_results.json saved")

    # Summary
    high_list = [s for s in scored_stocks if s["priority"] == "High"]
    medium_list = [s for s in scored_stocks if s["priority"] == "Medium"]
    low_count = len([s for s in scored_stocks if s["priority"] == "Low"])

    summary = (
        f"📊 *Scan Summary* — {datetime.now().strftime('%d %b %H:%M')}\n\n"
        f"Total unique stocks: *{len(stocks)}*\n"
        f"🔴 High Priority (≥6): *{len(high_list)}*\n"
        f"🟡 Medium Priority (4–5.9): *{len(medium_list)}*\n"
        f"⚪ Backend only (<4): *{low_count}*\n\n"
        "Sending High & Medium priority stocks..."
    )
    send_telegram(summary)

    # ===== HIGH PRIORITY MESSAGES =====
    if high_list:
        send_telegram("🔴 *HIGH PRIORITY STOCKS* (Score ≥ 6.0)\n" + "─" * 20)
        for i, s in enumerate(high_list[:12], 1):
            news_text = "\n".join(s["news"]) if s["news"] else "• No major news"
            msg = (
                f"🔴 *HIGH PRIORITY #{i}*\n"
                f"📊 *{s['name']}*\n"
                f"💰 ₹{s['price']}\n"
                f"⭐ Score: *{s['score']}/10*\n"
                f"🏷 `{s['screens_str']}`\n"
                f"{' | '.join(s['tags'])}\n"
                f"🔗 [Screener]({s['url']})\n\n"
                f"*News:*\n{news_text}"
            )
            send_telegram(msg)
            print(f"🔴 High: {s['name']} ({s['score']})")

    # ===== MEDIUM PRIORITY MESSAGES =====
    if medium_list:
        send_telegram("🟡 *MEDIUM PRIORITY STOCKS* (Score 4.0 – 5.9)\n" + "─" * 20)
        for i, s in enumerate(medium_list[:10], 1):
            news_text = "\n".join(s["news"]) if s["news"] else "• No major news"
            msg = (
                f"🟡 *MEDIUM PRIORITY #{i}*\n"
                f"📊 *{s['name']}*\n"
                f"💰 ₹{s['price']}\n"
                f"⭐ Score: *{s['score']}/10*\n"
                f"🏷 `{s['screens_str']}`\n"
                f"{' | '.join(s['tags'])}\n"
                f"🔗 [Screener]({s['url']})\n\n"
                f"*News:*\n{news_text}"
            )
            send_telegram(msg)
            print(f"🟡 Medium: {s['name']} ({s['score']})")

    final = (
        f"✅ *Scan Completed*\n\n"
        f"🔴 High Priority sent: {min(len(high_list), 12)}\n"
        f"🟡 Medium Priority sent: {min(len(medium_list), 10)}\n"
        f"⚪ Backend monitoring: {low_count}\n"
        f"📝 All stocks logged for performance tracking"
    )
    send_telegram(final)
    print("✅ Completed")

if __name__ == "__main__":
    main()
