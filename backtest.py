"""
backtest.py
-----------
Backtest the Swing Strategy on liquid NSE stocks.
Uses swing_strategy.py
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from swing_strategy import SwingStrategy

# ====================== CONFIG ======================
START_DATE = "2023-01-01"
END_DATE = datetime.now().strftime("%Y-%m-%d")

CAPITAL = 1_000_000
RISK_PCT = 0.01
MAX_OPEN_TRADES = 5
RR_RATIO = 3.0
MAX_HOLD_DAYS = 15

# Same universe used in swing_scanner.py
SYMBOLS = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS",
    "AXISBANK.NS", "INFY.NS", "TCS.NS", "HCLTECH.NS", "LT.NS",
    "ADANIPORTS.NS", "SUNPHARMA.NS", "DRREDDY.NS", "DIVISLAB.NS",
    "MARUTI.NS", "M&M.NS", "TITAN.NS", "BHARTIARTL.NS", "NTPC.NS",
    "POWERGRID.NS", "BAJFINANCE.NS", "TATAMOTORS.NS", "WIPRO.NS",
    "ULTRACEMCO.NS", "INDUSINDBK.NS"
]


def download_data(symbol: str) -> pd.DataFrame:
    """Download and clean daily data."""
    try:
        df = yf.download(
            symbol,
            start=START_DATE,
            end=END_DATE,
            progress=False,
            auto_adjust=True
        )
        if df.empty or len(df) < 100:
            return pd.DataFrame()

        # Flatten multi-index columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.dropna(inplace=True)
        return df
    except Exception as e:
        print(f"  ⚠️ Failed to download {symbol}: {e}")
        return pd.DataFrame()


def run_backtest():
    strategy = SwingStrategy(
        risk_pct=RISK_PCT,
        rr_ratio=RR_RATIO,
        max_hold_days=MAX_HOLD_DAYS
    )

    all_trades = []
    equity = float(CAPITAL)
    open_trades = []          # list of active trades

    print("=" * 60)
    print("🚀 Starting Swing Strategy Backtest")
    print(f"Period     : {START_DATE} → {END_DATE}")
    print(f"Capital    : ₹{CAPITAL:,}")
    print(f"Risk/Trade : {RISK_PCT*100}%")
    print("=" * 60)

    for symbol in SYMBOLS:
        print(f"Processing {symbol} ...")
        df = download_data(symbol)
        if df.empty:
            continue

        df = strategy.add_indicators(df)
        df = df.dropna()

        for i in range(60, len(df)):
            current_date = df.index[i]
            row = df.iloc[i]

            # ---------- 1. Manage open trades for this symbol ----------
            still_open = []
            for trade in open_trades:
                if trade["symbol"] != symbol:
                    still_open.append(trade)
                    continue

                days_held = (current_date - trade["entry_date"]).days
                exit_price = None
                exit_reason = None

                # Stop loss hit
                if row["Low"] <= trade["stop"]:
                    exit_price = trade["stop"]
                    exit_reason = "Stop Loss"

                # Target hit
                elif row["High"] >= trade["target"]:
                    exit_price = trade["target"]
                    exit_reason = "Target"

                # Time stop
                elif days_held >= MAX_HOLD_DAYS:
                    exit_price = row["Close"]
                    exit_reason = "Time Stop"

                if exit_price is not None:
                    pnl = (exit_price - trade["entry"]) * trade["shares"]
                    equity += pnl

                    all_trades.append({
                        "symbol": symbol,
                        "name": symbol.replace(".NS", ""),
                        "entry_date": trade["entry_date"].strftime("%Y-%m-%d"),
                        "exit_date": current_date.strftime("%Y-%m-%d"),
                        "entry": round(trade["entry"], 2),
                        "exit": round(exit_price, 2),
                        "stop": round(trade["stop"], 2),
                        "target": round(trade["target"], 2),
                        "shares": trade["shares"],
                        "pnl": round(pnl, 2),
                        "return_pct": round((exit_price / trade["entry"] - 1) * 100, 2),
                        "days_held": days_held,
                        "exit_reason": exit_reason,
                        "equity_after": round(equity, 2)
                    })
                else:
                    still_open.append(trade)

            open_trades = still_open

            # ---------- 2. Look for new entry ----------
            if len(open_trades) >= MAX_OPEN_TRADES:
                continue

            # We only check the latest available bar for signal
            # (using data up to current bar)
            window = df.iloc[:i+1]
            signal = strategy.generate_signal(window)

            if signal is None:
                continue

            shares = strategy.position_size(signal.entry, signal.stop, equity)
            if shares <= 0:
                continue

            # Avoid duplicate open position in same symbol
            if any(t["symbol"] == symbol for t in open_trades):
                continue

            open_trades.append({
                "symbol": symbol,
                "entry_date": current_date,
                "entry": signal.entry,
                "stop": signal.stop,
                "target": signal.target,
                "shares": shares
            })

    # ---------- Close any remaining open trades at last price ----------
    for trade in open_trades:
        # We don't have future data, so just mark them as open (or skip)
        pass

    return pd.DataFrame(all_trades), equity


def print_summary(trades_df: pd.DataFrame, final_equity: float):
    if trades_df.empty:
        print("\n❌ No trades were generated.")
        return

    total_trades = len(trades_df)
    winners = trades_df[trades_df["pnl"] > 0]
    losers = trades_df[trades_df["pnl"] <= 0]

    win_rate = len(winners) / total_trades * 100
    avg_win = winners["pnl"].mean() if not winners.empty else 0
    avg_loss = losers["pnl"].mean() if not losers.empty else 0
    total_pnl = trades_df["pnl"].sum()
    total_return = (final_equity / CAPITAL - 1) * 100

    # Approximate R-multiple
    risk_per_trade = CAPITAL * RISK_PCT
    trades_df["R"] = trades_df["pnl"] / risk_per_trade
    avg_r = trades_df["R"].mean()

    print("\n" + "=" * 60)
    print("📊 BACKTEST RESULTS")
    print("=" * 60)
    print(f"Total Trades        : {total_trades}")
    print(f"Win Rate            : {win_rate:.1f}%")
    print(f"Average R           : {avg_r:.2f}")
    print(f"Average Win         : ₹{avg_win:,.0f}")
    print(f"Average Loss        : ₹{avg_loss:,.0f}")
    print(f"Total PnL           : ₹{total_pnl:,.0f}")
    print(f"Final Equity        : ₹{final_equity:,.0f}")
    print(f"Total Return        : {total_return:.1f}%")
    print("-" * 60)
    print("Exit Reason Breakdown:")
    print(trades_df["exit_reason"].value_counts().to_string())
    print("=" * 60)

    # Save detailed trades
    trades_df.to_csv("backtest_trades.csv", index=False)
    print("✅ Detailed trades saved → backtest_trades.csv")

    # Save summary as JSON (useful for Streamlit later)
    summary = {
        "backtest_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "period": f"{START_DATE} to {END_DATE}",
        "total_trades": total_trades,
        "win_rate": round(win_rate, 1),
        "avg_r": round(avg_r, 2),
        "total_pnl": round(total_pnl, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return, 1)
    }

    import json
    with open("backtest_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("✅ Summary saved → backtest_summary.json")


if __name__ == "__main__":
    trades, final_equity = run_backtest()
    print_summary(trades, final_equity)