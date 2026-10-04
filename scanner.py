import os
import json
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime

def get_secret(key):
    val = os.environ.get(key)
    if val:
        return val
    try:
        from google.colab import userdata
        return userdata.get(key)
    except ImportError:
        return None

TELEGRAM_TOKEN = get_secret('TELEGRAM_TOKEN')
MY_CHAT_ID = get_secret('MY_CHAT_ID')
SCREENER_USERNAME = get_secret('SCREENER_USERNAME')
SCREENER_PASSWORD = get_secret('SCREENER_PASSWORD')

if not all([SCREENER_USERNAME, SCREENER_PASSWORD]):
    print("❌ Critical Screener secret resolution failed.")
    exit(1)

# ========== YOUR 8 SCREENS ==========
SCREENER_URLS = {
    "High Piotroski": "https://www.screener.in/screens/4000817/high-piotroski-score/",
    "Magic Formula": "https://www.screener.in/screens/4000836/magic-formula-greenblatt/",
    "Darvas Scan": "https://www.screener.in/screens/4000848/darvas-scan/",
    "Jim Slater Zulu": "https://www.screener.in/screens/4003190/jim-slater-zulu/",
    "Driehaus Momentum": "https://www.screener.in/screens/4004103/richard-driehaus-momentum-screen/",
    "Altman Z Score": "https://www.screener.in/screens/4005994/altman-z-score/",
    "Crash Recovery": "https://www.screener.in/screens/4009908/crash-recovery-screener/",
    "Quality 40-80": "https://www.screener.in/screens/2062976/penny-stocks/"
}

def get_screener_session():
    session = requests.Session()
    login_url = "https://www.screener.in/login/"
    try:
        init_res = session.get(login_url, timeout=15)
        soup = BeautifulSoup(init_res.text, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        if not csrf_token:
            print("❌ CSRF token not found")
            return None
        payload = {
            'username': SCREENER_USERNAME,
            'password': SCREENER_PASSWORD,
            'csrfmiddlewaretoken': csrf_token['value']
        }
        res = session.post(login_url, data=payload, headers={'Referer': login_url}, timeout=15)
        if "logout" in res.text.lower() or res.status_code == 200:
            print("✅ Screener login successful")
            return session
        else:
            print("❌ Screener login failed")
            return None
    except Exception as e:
        print(f"⚠️ Screener session error: {e}")
        return None

def scan_screener_urls(session):
    all_stocks = {}
    screen_counts = {}

    for screen_name, url in SCREENER_URLS.items():
        print(f"🔍 Scanning: {screen_name}")
        try:
            res = session.get(url, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            count = 0
            for row in soup.select("table.data-table tbody tr"):
                link_tag = row.select_one("td a")
                if link_tag and '/company/' in link_tag.get('href', ''):
                    name = link_tag.text.strip()
                    cols = row.find_all('td')
                    try:
                        price = cols[2].text.strip().replace(',', '') if len(cols) > 2 else "N/A"
                    except:
                        price = "N/A"
                    
                    if name not in all_stocks:
                        all_stocks[name] = {
                            'name': name,
                            'url': f"https://www.screener.in{link_tag['href']}",
                            'price': price,
                            'screens': []
                        }
                    if screen_name not in all_stocks[name]['screens']:
                        all_stocks[name]['screens'].append(screen_name)
                    count += 1
            screen_counts[screen_name] = count
            print(f"   → Found {count} stocks")
        except Exception as e:
            print(f"⚠️ Error scanning {screen_name}: {e}")
            screen_counts[screen_name] = 0

    print(f"✅ Total unique stocks found: {len(all_stocks)}")
    return all_stocks, screen_counts

def get_news_for_stock(stock_name):
    try:
        query = stock_name.replace(" ", "+")
        url = f"https://news.google.com/rss/search?q={query}+stock+OR+shares&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(url)
        
        positive_keywords = ['order', 'win', 'bag', 'contract', 'profit', 'rise', 'surge', 'growth', 
                             'expand', 'capacity', 'result', 'beat', 'acquire', 'partnership']
        negative_keywords = ['loss', 'fall', 'drop', 'decline', 'fraud', 'probe', 'penalty']

        news_items = []
        sentiment = "Neutral"

        for entry in feed.entries[:3]:
            title = entry.title
            title_lower = title.lower()
            if any(word in title_lower for word in positive_keywords):
                sentiment = "Positive"
                news_items.append(f"🟢 {title[:90]}")
            elif any(word in title_lower for word in negative_keywords):
                sentiment = "Negative"
                news_items.append(f"🔴 {title[:90]}")
            else:
                news_items.append(f"⚪ {title[:90]}")

        return sentiment, news_items[:2]
    except:
        return "Neutral", []

def send_telegram_message(text):
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
        print(f"❌ Telegram Error: {e}")
        return False

def main():
    print("🔄 Starting Heartbeat...")
    
    heartbeat_msg = (
        "❤️ *Guru Screener Bot Heartbeat*\n\n"
        "✅ Setup is working correctly!\n"
        f"📅 Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"📊 Screens Active: *8*\n"
        "• High Piotroski  • Magic Formula\n"
        "• Darvas  • Zulu  • Driehaus\n"
        "• Altman Z  • Crash Recovery\n"
        "• Quality 40-80\n\n"
        "News Intelligence: Active"
    )
    send_telegram_message(heartbeat_msg)

    screener_session = get_screener_session()
    if not screener_session:
        send_telegram_message("❌ *Screener login failed!* Check secrets.")
        return

    active_stocks, screen_counts = scan_screener_urls(screener_session)

    if not active_stocks:
        send_telegram_message("⚠️ No stocks found today.")
        return

    # ========== SAVE RESULTS FOR STREAMLIT ==========
    results_for_dashboard = {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_stocks": len(active_stocks),
        "screen_counts": screen_counts,
        "stocks": []
    }

    for name, details in active_stocks.items():
        results_for_dashboard["stocks"].append({
            "name": name,
            "price": details.get("price", "N/A"),
            "screens": ", ".join(details.get("screens", [])),
            "screen_count": len(details.get("screens", [])),
            "url": details.get("url", "")
        })

    # Sort by number of screens
    results_for_dashboard["stocks"] = sorted(
        results_for_dashboard["stocks"],
        key=lambda x: x["screen_count"],
        reverse=True
    )

    with open("scan_results.json", "w") as f:
        json.dump(results_for_dashboard, f, indent=2)
    print("✅ scan_results.json saved for Streamlit")

    # ========== TELEGRAM SUMMARY ==========
    summary = [f"📊 *Scan Summary* — {datetime.now().strftime('%d %b %Y %H:%M')}\n"]
    summary.append(f"✅ Total unique stocks: *{len(active_stocks)}*\n")
    for name, count in screen_counts.items():
        summary.append(f"• {name}: {count}")
    summary.append("\nSending top stocks with News...")
    send_telegram_message("\n".join(summary))

    # ========== SEND TOP STOCKS ==========
    sorted_stocks = sorted(
        active_stocks.items(),
        key=lambda x: len(x[1]['screens']),
        reverse=True
    )

    count = 0
    for name, details in sorted_stocks[:12]:
        count += 1
        price = details.get('price', 'N/A')
        url = details.get('url', '')
        screens = details.get('screens', [])
        screens_str = ", ".join(screens)

        sentiment, news_list = get_news_for_stock(name)
        news_text = "\n".join(news_list) if news_list else "• No major recent news"

        tags = []
        if "Crash Recovery" in screens:
            tags.append("🚀 Recovery")
        if "Quality 40-80" in screens:
            tags.append("💎 40-80")
        if len(screens) >= 3:
            tags.append("🔥 Multi-Screen")
        if sentiment == "Positive":
            tags.append("📰 News+")
        elif sentiment == "Negative":
            tags.append("⚠️ News-")

        tags_str = " | ".join(tags) if tags else ""

        msg = (
            f"📌 *Stock #{count}*\n"
            f"📊 *{name}*\n"
            f"💰 Price: ₹{price}\n"
            f"🏷 Screens: `{screens_str}`\n"
            f"{tags_str}\n"
            f"🔗 [Screener]({url})\n\n"
            f"*News:*\n{news_text}"
        )
        send_telegram_message(msg)
        print(f"🚀 Sent: {name}")

    final_msg = (
        f"✅ *Scan Completed*\n\n"
        f"Sent top {count} stocks.\n"
        f"Total: {len(active_stocks)}\n"
        f"Dashboard data saved."
    )
    send_telegram_message(final_msg)
    print("✅ Full scan completed")

if __name__ == "__main__":
    main()