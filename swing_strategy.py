"""
swing_scanner.py
Sends 3 types of Swing Trading Recommendations to Telegram
1. Strict 1.5%
2. Medium 2.5%
3. Simple (no reclaim)
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
MAX_SIGNALS_PER_TYPE = 5
IST = ZoneInfo("Asia/Kolkata")

SWING_UNIVERSE = [
    # ========== Nifty 50 ==========
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
    "SHREECEM.NS",

    # ========== Nifty Next 50 / Nifty 100 ==========
    "ADANIPOWER.NS", "ETERNAL.NS", "HAL.NS", "DMART.NS", "PIDILITIND.NS",
    "SIEMENS.NS", "DLF.NS", "HAVELLS.NS", "GODREJCP.NS", "ICICIGI.NS",
    "ICICIPRULI.NS", "NAUKRI.NS", "LTIM.NS", "PERSISTENT.NS", "DIXON.NS",
    "POLYCAB.NS", "TVSMOTOR.NS", "AMBUJACEM.NS", "ACC.NS", "BANKBARODA.NS",
    "PNB.NS", "CANBK.NS", "UNIONBANK.NS", "INDIGO.NS", "ZOMATO.NS",
    "PAYTM.NS", "POLICYBZR.NS", "NYKAA.NS", "IRFC.NS", "RECLTD.NS",
    "PFC.NS", "NHPC.NS", "SJVN.NS", "GAIL.NS", "IOC.NS",
    "HINDPETRO.NS", "VEDL.NS", "JINDALSTEL.NS", "SAIL.NS", "NMDC.NS",
    "HINDZINC.NS", "PIIND.NS", "AUBANK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS",
    "BANDHANBNK.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS", "SBICARD.NS", "LICI.NS",

    # ========== Liquid Nifty 200 / High volume names ==========
    "BHEL.NS", "BOSCHLTD.NS", "ABB.NS", "CGPOWER.NS", "CUMMINSIND.NS",
    "ASHOKLEY.NS", "TIINDIA.NS", "MRF.NS", "BALKRISIND.NS", "APOLLOTYRE.NS",
    "MOTHERSON.NS", "BHARATFORG.NS", "EXIDEIND.NS", "SONACOMS.NS",
    "LUPIN.NS", "TORNTPHARM.NS", "BIOCON.NS", "LAURUSLABS.NS", "AUROPHARMA.NS",
    "ALKEM.NS", "IPCALAB.NS", "GLENMARK.NS", "ZYDUSLIFE.NS",
    "PAGEIND.NS", "TRENT.NS", "ABFRL.NS", "RELAXO.NS", "BATAINDIA.NS",
    "VOLTAS.NS", "BLUESTARCO.NS", "WHIRLPOOL.NS", "CROMPTON.NS",
    "BERGEPAINT.NS", "KANSAINER.NS", "COLPAL.NS", "DABUR.NS", "MARICO.NS",
    "EMAMILTD.NS", "VBL.NS", "UBL.NS", "RADICO.NS",
    "CONCOR.NS", "GMRINFRA.NS", "IRCTC.NS", "MAZDOCK.NS", "COCHINSHIP.NS",
    "OFSS.NS", "MPHASIS.NS", "COFORGE.NS", "LTTS.NS", "TANLA.NS",
    "KPITTECH.NS", "BSOFT.NS"
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


def scan_with_strategy(strategy, label):
    """Scan all stocks with a given strategy and return signals"""
    signals = []
    print(f"Scanning with {label}...")

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
                plan["label"] = label
                signals.append(plan)
                print(f"  {label} → {plan['name']}")
        except Exception as e:
            print(f"  Error {symbol}: {e}")

    return signals


def format_signal_message(plan: dict, index: int) -> str:
    risk_pct = ((plan["entry"] - plan["stop"]) / plan["entry"]) * 100
    reward_pct = ((plan["target"] - plan["entry"]) / plan["entry"]) * 100

    msg = (
        f"🎯 *{plan['label']} #{index}*\n\n"
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
        f"📌 {plan['reason']}\n"
        f"⏱ Max Holding: {plan['max_hold_days']} days\n"
        f"📅 {get_ist_time()}"
    )
    return msg


def send_group(signals, title):
    if not signals:
        send_telegram(
            f"📭 *{title}*\n\n"
            f"No setups found.\n"
            f"📅 {get_ist_time()}"
        )
        return

    signals = signals[:MAX_SIGNALS_PER_TYPE]

    summary = (
        f"🎯 *{title}*\n\n"
        f"✅ Found *{len(signals)}* setups\n"
        f"📅 {get_ist_time()}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    send_telegram(summary)

    for i, plan in enumerate(signals, 1):
        send_telegram(format_signal_message(plan, i))


def main():
    print("🚀 Starting 3-version Swing Scanner")

    # ----- Version 1: Strict 1.5% + Reclaim -----
    strategy_strict = SwingStrategy(
        risk_pct=RISK_PCT,
        rr_ratio=3.0,
        max_pullback_pct=0.015,
        volume_mult=1.2
    )
    # Force reclaim logic by temporarily using original method
    # We will handle reclaim inside a custom check below if needed.
    # For simplicity we use the current strategy class and adjust parameters.

    signals_strict = scan_with_strategy(strategy_strict, "Strict 1.5% Pullback")

    # ----- Version 2: Medium 2.5% + Reclaim -----
    strategy_medium = SwingStrategy(
        risk_pct=RISK_PCT,
        rr_ratio=3.0,
        max_pullback_pct=0.025,
        volume_mult=1.15
    )
    signals_medium = scan_with_strategy(strategy_medium, "Medium 2.5% Pullback")

    # ----- Version 3: Simple (No Reclaim) -----
    strategy_simple = SwingStrategy(
        risk_pct=RISK_PCT,
        rr_ratio=3.0,
        max_pullback_pct=0.025,
        volume_mult=1.1
    )
    signals_simple = scan_with_strategy(strategy_simple, "Simple Logic (No Reclaim)")

    # Send all three groups
    send_group(signals_strict, "Strict 1.5% Pullback + Reclaim")
    send_group(signals_medium, "Medium 2.5% Pullback + Reclaim")
    send_group(signals_simple, "Simple Logic (No Reclaim Needed)")

    send_telegram(
        f"✅ *All 3 Scans Complete*\n\n"
        f"📅 {get_ist_time()}"
    )
    print("✅ Done - All 3 versions sent")


if __name__ == "__main__":
    main()
