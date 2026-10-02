import os
import io
import json
import requests
import pandas as pd
import feedparser
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
import re
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
DSIJ_USERNAME = get_secret('DSIJ_USERNAME')
DSIJ_PASSWORD = get_secret('DSIJ_PASSWORD')
DISCORD_WEBHOOK_URL = get_secret('DISCORD_WEBHOOK_URL')

if not all([SCREENER_USERNAME, SCREENER_PASSWORD]):
    print("❌ Critical Screener secret resolution failed.")
    exit(1)

# ========== YOUR 6 GURU SCREENS ==========
SCREENER_URLS = [
    "https://www.screener.in/screens/4000817/high-piotroski-score/",
    "https://www.screener.in/screens/4000836/magic-formula-greenblatt/",
    "https://www.screener.in/screens/4000848/darvas-scan/",
    "https://www.screener.in/screens/4003190/jim-slater-zulu/",
    "https://www.screener.in/screens/4004103/richard-driehaus-momentum-screen/",
    "https://www.screener.in/screens/4005994/altman-z-score/"
]

HISTORY_FILE = "holdings_history.json"
CHARTS_DIR = "charts"

if not os.path.exists(CHARTS_DIR):
    os.makedirs(CHARTS_DIR)

if os.path.exists(HISTORY_FILE) and os.path.getsize(HISTORY_FILE) > 0:
    with open(HISTORY_FILE, "r") as f:
        try:
            historical_db = json.load(f)
        except json.JSONDecodeError:
            historical_db = {}
else:
    historical_db = {}

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
    for url in SCREENER_URLS:
        print(f"🔍 Scanning: {url}")
        try:
            res = session.get(url, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            for row in soup.select("table.data-table tbody tr"):
                link_tag = row.select_one("td a")
                if link_tag and '/company/' in link_tag.get('href', ''):
                    name = link_tag.text.strip()
                    cols = row.find_all('td')
                    try:
                        price = cols[2].text.strip().replace(',', '') if len(cols) > 2 else "N/A"
                    except:
                        price = "N/A"
                    all_stocks[name] = {
                        'url': f"https://www.screener.in{link_tag['href']}",
                        'price': price
                    }
        except Exception as e:
            print(f"⚠️ Error scanning {url}: {e}")
    print(f"✅ Total unique stocks found: {len(all_stocks)}")
    return all_stocks

def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not MY_CHAT_ID:
        print("❌ Telegram credentials missing")
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
        print(f"Telegram response: {res.status_code}")
        return res.status_code == 200
    except Exception as e:
        print(f"❌ Telegram Error: {e}")
        return False

def main():
    # ========== HEARTBEAT ==========
    print("🔄 Starting Heartbeat Test...")
    
    heartbeat_msg = (
        "❤️ *Guru Screener Bot Heartbeat*\n\n"
        "✅ Setup is working correctly!\n"
        f"📅 Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"📊 Screens Active: *6*\n"
        "• High Piotroski Score\n"
        "• Magic Formula Greenblatt\n"
        "• Darvas Scan\n"
        "• Jim Slater Zulu\n"
        "• Richard Driehaus Momentum\n"
        "• Altman Z Score > 3\n\n"
        "Bot is ready and monitoring stocks."
    )
    
    send_telegram_message(heartbeat_msg)
    print("🔄 Heartbeat sent. Starting full scan...")

    # ========== LOGIN & SCAN ==========
    screener_session = get_screener_session()
    if not screener_session:
        send_telegram_message("❌ *Screener login failed!* Please check username/password secrets.")
        return

    active_stocks = scan_screener_urls(screener_session)

    if not active_stocks:
        send_telegram_message("⚠️ No stocks found in any screen today.")
        return

    # ========== SUMMARY MESSAGE ==========
    summary = (
        f"📊 *Scan Summary*\n\n"
        f"✅ Total unique stocks found: *{len(active_stocks)}*\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Sending top stocks below..."
    )
    send_telegram_message(summary)

    # ========== SEND STOCK REPORTS (limit to 12) ==========
    count = 0
    for name, details in list(active_stocks.items())[:12]:
        count += 1
        price = details.get('price', 'N/A')
        url = details.get('url', '')

        msg = (
            f"📌 *Stock #{count}*\n"
            f"📊 *{name}*\n"
            f"💰 Price: ₹{price}\n"
            f"🔗 [View on Screener]({url})\n\n"
            f"_Appeared in Guru Screens_"
        )
        
        success = send_telegram_message(msg)
        if success:
            print(f"🚀 Sent report for {name}")
        else:
            print(f"❌ Failed to send {name}")

    # Final message
    final_msg = (
        f"✅ *Scan Completed*\n\n"
        f"Sent reports for top {count} stocks.\n"
        f"Total stocks in screens: {len(active_stocks)}\n\n"
        f"Bot will run again on next schedule."
    )
    send_telegram_message(final_msg)

    print("✅ Full scan completed")

if __name__ == "__main__":
    main()