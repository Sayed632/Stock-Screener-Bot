"""
swing_scanner.py
Sends Swing Trading Recommendations to Telegram (with Indian Time)
"""

import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from swing_strategy import SwingStrategy


def get_secret(key):
    return os.environ.get(key)


TELEGRAM_TOKEN = get_secret("TELEGRAM_TOKEN")
MY_CHAT_ID = get_secret("MY_CHAT_ID")

if not TELEGRAM_TOKEN or not MY_CHAT_ID:
    print("❌ Telegram secrets missing")
    exit(1)


CAPITAL = 1_000_000
RISK_PCT = 0.01
MAX_SIGNALS_TO_SEND = 8

# Indian Timezone
IST = ZoneInfo("Asia/Kolkata")

SWING_UNIVERSE = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS",
    "AXISBANK.NS", "INFY.NS", "TCS.NS", "HCLTECH.NS", "LT.NS",
    "ADANIPORTS.NS", "SUNPHARMA.NS", "DRREDDY.NS", "DIVISLAB.NS",
    "MARUTI.NS", "M&M.NS", "TITAN.NS", "BHARTIARTL.NS", "NTPC.NS",
    "POWERGRID.NS", "BAJFINANCE.NS", "TATAMOTORS.NS", "WIPRO.NS",
    "ULTRACEMCO.NS", "INDUSINDBK.NS"
]


def get_ist_time():
    """Return current time in Indian Standard Time"""
    return datetime.now(IST).strftime('%d %b %Y • %I:%M %p IST')


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": MY_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"Telegram error: {e}")


def get_clean_name(symbol: str) -> str:
    return symbol.replace(".NS", "").replace(".BO", "")


def scan_swing_setups():
    strategy = SwingStrategy(risk_pct=RISK_PCT, rr_ratio=3.0)
    signals = []

    print(f"Scanning {len(SWING_UNIVERSE)} stocks...")

    for symbol in SWING_UNIVERSE:
        try:
            df = yf.download(symbol, period="6mo", interval="1d",
                             progress=False, auto_adjust=True)

            if df.empty or len(df) < 60:
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            plan = strategy.get_trade_plan(df, capital=CAPITAL)

            if plan:
                plan["symbol"] = symbol
                plan["name"] = get_clean_name(symbol)
                signals.append(plan)
                print(f"  Setup found: {plan['name']}")
        except Exception as e:
            print(f"  Error {symbol}: {e}")

    return signals


def format_signal_message(plan: dict, index: int) -> str:
    risk_pct = ((plan["entry"] - plan["stop"]) / plan["entry"]) * 100
    reward_pct = ((plan["target"] - plan["entry"]) / plan["entry"]) * 100

    msg = (
        f"🎯 *Swing Trading Recommendation #{index}*\n\n"
        f"📊 *{plan['name']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 *Entry*     : ₹{plan['entry']}\n"
        f"🔴 *Stop Loss* : ₹{plan['stop']}  ({risk_pct:.1f}%)\n"
        f"🎯 *Target*    : ₹{plan['target']}  ({reward_pct:.1f}%)\n"
        f"📈 *Risk:Reward* : 1 : {plan['rr_ratio']}\n"
        f"📦 *Quantity*  : {plan['shares']} shares\n"
        f"💰 *Risk Amount* : ₹{plan['risk_amount']:,.0f}\n"
        f"💎 *Reward Potential* : ₹{plan['reward_amount']:,.0f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Strategy: Trend + Near EMA20 + Volume\n"
        f"⏱ Max Holding: {plan['max_hold_days']} days\n"
        f"📅 {get_ist_time()}"
    )
    return msg


def main():
    print("🚀 Swing Trading Scanner Started")
    signals = scan_swing_setups()

    if not signals:
        send_telegram(
            "📭 *Swing Trading Scanner*\n\n"
            "No high-quality swing setups found today.\n\n"
            f"Checked {len(SWING_UNIVERSE)} liquid stocks.\n"
            f"📅 {get_ist_time()}"
        )
        print("No setups found.")
        return

    signals = signals[:MAX_SIGNALS_TO_SEND]

    summary = (
        f"🎯 *Swing Trading Recommendations*\n\n"
        f"✅ Found *{len(signals)}* high-quality setups\n"
        f"💰 Capital : ₹{CAPITAL:,}\n"
        f"⚠️ Risk per trade : {RISK_PCT*100}%\n"
        f"📅 {get_ist_time()}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    send_telegram(summary)

    for i, plan in enumerate(signals, 1):
        send_telegram(format_signal_message(plan, i))
        print(f"Sent: {plan['name']}")

    send_telegram(
        f"✅ *Swing Scan Complete*\n\n"
        f"Total recommendations sent: *{len(signals)}*\n"
        f"📅 {get_ist_time()}"
    )
    print("✅ Done")


if __name__ == "__main__":
    main()