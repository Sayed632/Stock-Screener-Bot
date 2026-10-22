"""
swing_scanner.py
Sends Swing Trading Recommendations to Telegram (with Indian Time)
+ Logs recommendations for performance tracking
Expanded Universe: Nifty 50 + Nifty 100 + Liquid Nifty 200
"""

import os
import json
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
MAX_SIGNALS_TO_SEND = 10
IST = ZoneInfo("Asia/Kolkata")

SWING_UNIVERSE = [
    # Nifty 50
    "RELIANCE.NS", "HDFCBANK.NS", "BHARTIARTL.NS", "ICICIBANK.NS", "SBIN.NS",
    "TCS.NS", "BAJFINANCE.NS", "LT.NS", "HINDUNILVR.NS", "SUNPHARMA.NS",
    "KOTAKBANK.NS", "INFY.NS", "ADANIPORTS.NS", "TITAN.NS", "AXISBANK.NS",
    "MARUTI.NS", "M&M.NS", "ITC.NS", "HCLTECH.NS", "NTPC.NS",
    "ULTRACEMCO.NS", "TATAMOTORS.NS", "POWERGRID.NS", "BAJAJFINSV.NS",
    "ASIANPAINT.NS", "ONGC.NS", "NESTLEIND.NS", "WIPRO.NS", "COALINDIA.NS",
    "JSWSTEEL.NS", "BAJAJ-AUTO.NS", "ADANIENT.NS", "TECHM.NS", "HINDALCO.NS",
    "GRASIM.NS", "INDUSINDBK.NS", "CIPLA.NS", "DRREDDY.NS", "EICHERMOT.NS",
    "APOLLOHOSP.NS", "BEL.NS", "TATASTEEL.NS", "SBILIFE.NS", "HDFCLIFE.NS",
    "DIVISLAB.NS", "BPCL.NS", "BRITANNIA.NS", "HEROMOTOCO.NS", "TATACONSUM.NS",

    # Nifty 100 / Next 50
    "ADANIPOWER.NS", "HAL.NS", "DMART.NS", "PIDILITIND.NS", "SIEMENS.NS",
    "DLF.NS", "HAVELLS.NS", "GODREJCP.NS", "ICICIGI.NS", "ICICIPRULI.NS",
    "NAUKRI.NS", "LTIM.NS", "PERSISTENT.NS", "DIXON.NS", "POLYCAB.NS",
    "TVSMOTOR.NS", "AMBUJACEM.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS",
    "INDIGO.NS", "IRFC.NS", "RECLTD.NS", "PFC.NS", "NHPC.NS",
    "GAIL.NS", "IOC.NS", "VEDL.NS", "JINDALSTEL.NS", "SAIL.NS",
    "NMDC.NS", "PIIND.NS", "AUBANK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS",
    "CHOLAFIN.NS", "MUTHOOTFIN.NS", "SBICARD.NS",

    # Liquid Nifty 200
    "BHEL.NS", "ABB.NS", "CGPOWER.NS", "CUMMINSIND.NS", "ASHOKLEY.NS",
    "MRF.NS", "APOLLOTYRE.NS", "MOTHERSON.NS", "BHARATFORG.NS",
    "LUPIN.NS", "TORNTPHARM.NS", "AUROPHARMA.NS", "ALKEM.NS", "ZYDUSLIFE.NS",
    "PAGEIND.NS", "TRENT.NS", "VOLTAS.NS", "CROMPTON.NS", "BERGEPAINT.NS",
    "COLPAL.NS", "DABUR.NS", "MARICO.NS", "VBL.NS",
    "CONCOR.NS", "IRCTC.NS", "MAZDOCK.NS", "OFSS.NS", "MPHASIS.NS",
    "COFORGE.NS", "LTTS.NS", "KPITTECH.NS"
]


def get_ist_time():
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


def log_recommendation(name, entry_price, screens=None):
    """Save recommendation to performance_log.json"""
    log_file = "performance_log.json"
    try:
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                log = json.load(f)
        else:
            log = []
    except:
        log = []

    today = datetime.now(IST).strftime("%Y-%m-%d")
    
    # Avoid duplicate for same stock on same day
    for entry in log:
        if entry.get("name") == name and entry.get("date") == today:
            return

    log.append({
        "date": today,
        "name": name,
        "entry_price": entry_price,
        "screens": screens or ["Swing"]
    })

    with open(log_file, "w") as f:
        json.dump(log, f, indent=2)
    
    print(f"📝 Logged: {name} @ ₹{entry_price}")


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
                
                # Log for performance tracking
                log_recommendation(plan["name"], plan["entry"], screens=["Swing"])
                
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
            f"Checked {len(SWING_UNIVERSE)} stocks.\n"
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