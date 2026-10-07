"""
swing_strategy.py
Version 3 - No perfect reclaim required
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class Signal:
    entry: float
    stop: float
    target: float
    risk_per_share: float
    reward_per_share: float
    rr_ratio: float
    reason: str
    atr: float


class SwingStrategy:
    def __init__(
        self,
        risk_pct: float = 0.01,
        rr_ratio: float = 3.0,
        ema_fast: int = 20,
        ema_slow: int = 50,
        atr_period: int = 14,
        atr_multiplier: float = 2.5,
        max_pullback_pct: float = 0.025,
        volume_mult: float = 1.1,
        max_hold_days: int = 15,
    ):
        self.risk_pct = risk_pct
        self.rr_ratio = rr_ratio
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.max_pullback_pct = max_pullback_pct
        self.volume_mult = volume_mult
        self.max_hold_days = max_hold_days

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = [c.capitalize() for c in df.columns]

        df["EMA20"] = df["Close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["EMA50"] = df["Close"].ewm(span=self.ema_slow, adjust=False).mean()

        tr = pd.concat([
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs()
        ], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(self.atr_period).mean()
        df["Vol_MA20"] = df["Volume"].rolling(20).mean()
        df["EMA50_rising"] = df["EMA50"] > df["EMA50"].shift(1)

        return df

    def generate_signal(self, df: pd.DataFrame) -> Optional[Signal]:
        if len(df) < self.ema_slow + 5:
            return None

        df = self.add_indicators(df)
        df = df.dropna()

        if len(df) < 2:
            return None

        curr = df.iloc[-1]

        if not (curr["Close"] > curr["EMA50"] and curr["EMA50_rising"]):
            return None

        distance_to_ema20 = abs(curr["Close"] - curr["EMA20"]) / curr["EMA20"]
        near_ema20 = distance_to_ema20 <= self.max_pullback_pct
        volume_ok = curr["Volume"] >= (curr["Vol_MA20"] * self.volume_mult)

        if not (near_ema20 and volume_ok):
            return None

        entry = float(curr["Close"])
        structural_stop = float(curr["Low"])
        atr_stop = entry - (self.atr_multiplier * float(curr["ATR"]))
        stop = max(structural_stop, atr_stop)

        if stop >= entry:
            stop = entry - (1.5 * float(curr["ATR"]))

        risk_per_share = entry - stop
        if risk_per_share <= 0:
            return None

        target = entry + (risk_per_share * self.rr_ratio)

        return Signal(
            entry=round(entry, 2),
            stop=round(stop, 2),
            target=round(target, 2),
            risk_per_share=round(risk_per_share, 2),
            reward_per_share=round(target - entry, 2),
            rr_ratio=self.rr_ratio,
            reason="Trend + Near EMA20 (no reclaim needed) + Volume",
            atr=round(float(curr["ATR"]), 2),
        )

    def position_size(self, entry: float, stop: float, capital: float) -> int:
        risk_amount = capital * self.risk_pct
        risk_per_share = abs(entry - stop)
        if risk_per_share <= 0:
            return 0
        shares = int(risk_amount / risk_per_share)
        return max(shares, 0)

    def get_trade_plan(self, df: pd.DataFrame, capital: float) -> Optional[dict]:
        signal = self.generate_signal(df)
        if signal is None:
            return None

        shares = self.position_size(signal.entry, signal.stop, capital)
        if shares == 0:
            return None

        return {
            "entry": signal.entry,
            "stop": signal.stop,
            "target": signal.target,
            "shares": shares,
            "risk_amount": round(shares * signal.risk_per_share, 2),
            "reward_amount": round(shares * signal.reward_per_share, 2),
            "rr_ratio": signal.rr_ratio,
            "reason": signal.reason,
            "atr": signal.atr,
            "max_hold_days": self.max_hold_days,
        }