"""
swing_scanner.py
----------------
Technical Swing Trading Scanner
Sends recommendations to Telegram with clear heading.
Uses existing TELEGRAM_TOKEN and MY_CHAT_ID secrets.
"""

import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
from swing_strategy import SwingStrategy


# ========== Secrets (same style as your scanner.py) ==========
def get_secret(key):
    return os.environ.get(key)


TELEGRAM_TOKEN = get_secret("TELEGRAM_TOKEN")
MY_CHAT_ID = get_secret("MY_CHAT_ID")

if not TELEGRAM_TOKEN or not MY_CHAT_ID:
    print("❌ Telegram secrets missing (TELEGRAM_TOKEN / MY_CHAT_ID)")
    exit(1)


# ========== Config ==========
CAPITAL = 1_000_000          # Your capital
RISK_PCT = 0.01              # 1% risk per trade
MAX_SIGNALS_TO_SEND = 8      # Max messages to send

# Highly liquid NSE stocks suitable for swing trading
SWING_UNIVERSE = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS",
    "AXISBANK.NS", "INFY.NS", "TCS.NS", "HCLTECH.NS", "LT.NS",
    "ADANIPORTS.NS", "SUNPHARMA.NS", "DRREDDY.NS", "DIVISLAB.NS",
    "MARUTI.NS", "M&M.NS", "TITAN.NS", "BHARTIARTL.NS", "NTPC.NS",
    "POWERGRID.NS", "BAJFINANCE.NS", "TATAMOTORS.NS", "WIPRO.NS",
    "ULTRACEMCO.NS", "INDUSINDBK.NS"
]


def send_telegram(message: str):
    """Send message to your Telegram chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": MY_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code != 200:
            print(f"⚠️ Telegram error: {res.text}")
    except Exception as e:
        print(f"⚠️ Failed to send Telegram message: {e}")


def get_clean_name(symbol: str) -> str:
    """Convert RELIANCE.NS → RELIANCE"""
    return symbol.replace(".NS", "").replace(".BO", "")


def scan_swing_setups():
    """Scan all stocks and return valid swing signals."""
    strategy = SwingStrategy(risk_pct=RISK_PCT, rr_ratio=3.0)
    signals = []

    print(f"🔍 Scanning {len(SWING_UNIVERSE)} stocks for swing setups...")

    for symbol in SWING_UNIVERSE:
        try:
            df = yf.download(
                symbol,
                period="6mo",
                interval="1d",
                progress=False,
                auto_adjust=True
            )

            if df.empty or len(df) < 60:
                continue

            # Handle multi-index columns from yfinance
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            plan = strategy.get_trade_plan(df, capital=CAPITAL)

            if plan:
                plan["symbol"] = symbol
                plan["name"] = get_clean_name(symbol)
                signals.append(plan)
                print(f"  ✅ Setup found → {plan['name']}")

        except Exception as e:
            print(f"  ⚠️ Error on {symbol}: {e}")
            continue

    return signals


def format_signal_message(plan: dict, index: int) -> str:
    """Create a clean Telegram message for one recommendation."""
    name = plan["name"]
    entry = plan["entry"]
    stop = plan["stop"]
    target = plan["target"]
    shares = plan["shares"]
    risk_amt = plan["risk_amount"]
    reward_amt = plan["reward_amount"]
    rr = plan["rr_ratio"]

    risk_pct = ((entry - stop) / entry) * 100
    reward_pct = ((target - entry) / entry) * 100

    msg = (
        f"🎯 *Swing Trading Recommendation #{index}*\n\n"
        f"📊 *{name}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 *Entry*     : ₹{entry}\n"
        f"🔴 *Stop Loss* : ₹{stop}  ({risk_pct:.1f}%)\n"
        f"🎯 *Target*    : ₹{target}  ({reward_pct:.1f}%)\n"
        f"📈 *Risk:Reward* : 1 : {rr}\n"
        f"📦 *Quantity*  : {shares} shares\n"
        f"💰 *Risk Amount* : ₹{risk_amt:,.0f}\n"
        f"💎 *Reward Potential* : ₹{reward_amt:,.0f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Strategy: Trend + EMA20 Pullback + Volume\n"
        f"⏱ Max Holding Period: {plan['max_hold_days']} trading days\n"
        f"📅 {datetime.now().strftime('%d %b %Y • %I:%M %p')}"
    )
    return msg


def main():
    print("=" * 55)
    print("🚀 Swing Trading Scanner Started")
    print("=" * 55)

    signals = scan_swing_setups()

    if not signals:
        no_setup_msg = (
            "📭 *Swing Trading Scanner*\n\n"
            "No high-quality swing setups found today.\n\n"
            f"Checked {len(SWING_UNIVERSE)} liquid stocks.\n"
            f"📅 {datetime.now().strftime('%d %b %Y • %I:%M %p')}"
        )
        send_telegram(no_setup_msg)
        print("❌ No setups found today.")
        return

    # Limit number of signals
    signals = signals[:MAX_SIGNALS_TO_SEND]

    # 1. Send Summary first
    summary = (
        f"🎯 *Swing Trading Recommendations*\n\n"
        f"✅ Found *{len(signals)}* high-quality setups\n"
        f"💰 Capital : ₹{CAPITAL:,}\n"
        f"⚠️ Risk per trade : {RISK_PCT*100}%\n"
        f"📅 {datetime.now().strftime('%d %b %Y • %I:%M %p')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    send_telegram(summary)

    # 2. Send individual recommendations
    for i, plan in enumerate(signals, 1):
        msg = format_signal_message(plan, i)
        send_telegram(msg)
        print(f"📤 Sent to Telegram → {plan['name']}")

    # 3. Final confirmation
    final_msg = (
        f"✅ *Swing Scan Complete*\n\n"
        f"Total recommendations sent: *{len(signals)}*\n"
        f"Strategy: Trend + EMA20 Pullback + Volume Confirmation"
    )
    send_telegram(final_msg)

    print("=" * 55)
    print("✅ All Swing Trading recommendations sent to Telegram")
    print("=" * 55)


if __name__ == "__main__":
    main()