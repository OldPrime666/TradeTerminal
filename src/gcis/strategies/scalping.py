"""
Scalping strategy — P18 quick mean-reversion on 1m/5m with volume profile + orderbook imbalance.
Config: strategy.scalping {enabled, timeframe 1m, lookback 20, vol_profile_bins 24, imbalance_threshold 0.3, atr_stop 0.8, tp_r 1.2, min_score 55}
Deterministic, causal.
"""
from decimal import Decimal
from typing import List
import pandas as pd
from gcis.strategies.base import StrategyResult
from gcis.market.volume_profile import compute_volume_profile
from gcis.market.indicators import atr_wilder
from gcis.market.orderbook import get_book

STRATEGY_VERSION = "0.3.0"

def evaluate_scalping(view, symbol: str, config: dict) -> StrategyResult:
    strat_cfg = config.get("strategy",{}).get("scalping", {"enabled": True, "timeframe":"1m","lookback":20,"vol_profile_bins":24,"imbalance_threshold":0.3,"atr_stop":0.8,"tp_r":1.2,"min_score":55})
    if not strat_cfg.get("enabled", True):
        return StrategyResult("SCALPING","0.3.0", False, None, 0, 0.0, False, None, None, None, ["DISABLED"], ["DISABLED"], ["1m"], view.quality_state(symbol))
    tf = strat_cfg.get("timeframe","1m")
    df = view.get_closed_candles(symbol, tf)
    if df.empty or len(df) < strat_cfg.get("lookback",20)+10:
        return StrategyResult("SCALPING","0.3.0", False, None, 0, 0.0, False, None, None, None, ["INSUFFICIENT_HISTORY"], ["INSUFFICIENT_HISTORY"], [tf], view.quality_state(symbol))
    # Volume profile POC distance
    # Build candles list for profile: need last lookback candles
    lookback = strat_cfg.get("lookback",20)
    window = df.tail(lookback)
    candles = window.to_dict("records")
    # Convert Decimal if needed to float for profile but keep Decimal for zone?
    # Ensure dict has high/low/close/volume as float
    for c in candles:
        for k in ["high","low","close","volume"]:
            try:
                c[k] = float(c[k])
            except:
                pass
    vp = compute_volume_profile(candles, bins=strat_cfg.get("vol_profile_bins",24))
    if vp["status"]!="OK":
        return StrategyResult("SCALPING","0.3.0", False, None, 20, 0.2, True, None, None, None, [f"VP {vp['status']}"], ["NO_CLEAR_ENTRY"], [tf], view.quality_state(symbol))
    poc = vp["poc"]
    va_low = vp["value_area"]["low"]
    va_high = vp["value_area"]["high"]
    last_close = float(df.iloc[-1]["close"])
    # Orderbook imbalance if available
    ob = get_book(symbol)
    imb = ob.imbalance()
    if imb is None:
        imb = 0.0
    # Scalping logic: price near POC value area edge with imbalance confirming reversion
    # LONG if price < va_low and imb > threshold (bid heavy) => reversion up to POC
    # SHORT if price > va_high and imb < -threshold (ask heavy)
    thresh = strat_cfg.get("imbalance_threshold",0.3)
    direction = None
    if last_close < va_low and imb > thresh:
        direction = "LONG"
    elif last_close > va_high and imb < -thresh:
        direction = "SHORT"
    else:
        # also consider virgin POC test without imbalance but with distance
        dist_to_poc = abs(last_close - poc)
        atr_series = atr_wilder(window["high"], window["low"], window["close"], 14)
        atr = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else last_close*0.01
        if last_close < va_low and last_close < poc - atr*0.5:
            direction = "LONG"
        elif last_close > va_high and last_close > poc + atr*0.5:
            direction = "SHORT"
    if direction is None:
        return StrategyResult("SCALPING","0.3.0", False, None, 30, 0.3, True, None, None, None, [f"no scalping edge close {last_close:.2f} poc {poc:.2f} va [{va_low:.2f},{va_high:.2f}] imb {imb:.2f}"], ["NO_CLEAR_ENTRY"], [tf], view.quality_state(symbol))
    # entry zone around close +/-0.1 ATR, stop beyond VA edge +/-0.5 ATR, tp to POC
    atr_series = atr_wilder(df["high"], df["low"], df["close"], 14)
    atr = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else last_close*0.01
    entry = Decimal(str(last_close))
    # zone +/-0.1 ATR
    zone_low = entry - Decimal(str(atr*0.1))
    zone_high = entry + Decimal(str(atr*0.1))
    entry_zone = (zone_low, zone_high)
    atr_stop = strat_cfg.get("atr_stop",0.8)
    tp_r = strat_cfg.get("tp_r",1.2)
    if direction=="LONG":
        stop = Decimal(str(va_low)) - Decimal(str(atr*0.5)) if va_low < float(entry) else entry - Decimal(str(atr*atr_stop))
        if stop >= entry:
            stop = entry - Decimal(str(atr*atr_stop))
        # tp to POC or 1.2R
        risk = float(entry - stop)
        tp_poc = Decimal(str(poc))
        tp_r_price = entry + Decimal(str(risk*tp_r))
        # choose closer to ensure realistic
        tp = tp_poc if abs(float(tp_poc-entry)) < abs(float(tp_r_price-entry))*1.5 else tp_r_price
    else:
        stop = Decimal(str(va_high)) + Decimal(str(atr*0.5)) if va_high > float(entry) else entry + Decimal(str(atr*atr_stop))
        if stop <= entry:
            stop = entry + Decimal(str(atr*atr_stop))
        risk = float(stop - entry)
        tp_poc = Decimal(str(poc))
        tp_r_price = entry - Decimal(str(risk*tp_r))
        tp = tp_poc if abs(float(tp_poc-entry)) < abs(float(tp_r_price-entry))*1.5 else tp_r_price
    # cost check
    taker = config.get("costs",{}).get("taker_fee_bps",5)
    slip = config.get("costs",{}).get("slippage_bps_base",2)
    total_cost_bps = (taker*2 + slip)/10000
    cost = float(entry)*total_cost_bps
    risk = float(entry - stop) if direction=="LONG" else float(stop - entry)
    # net RR to poc
    tp_float = float(tp)
    reward = abs(tp_float - float(entry)) - cost
    net_r = reward/(risk+cost) if risk else 0
    min_score = strat_cfg.get("min_score",55)
    # scoring: base 50 + imbalance boost + distance to POC
    score = 50
    if abs(imb) > thresh:
        score += 10
    if vp["poc"]:
        dist_norm = abs(last_close - poc)/atr if atr else 0
        score += min(15, int(dist_norm*5))
    if net_r >1.0:
        score +=5
    score = min(85, score)
    if score < min_score:
        return StrategyResult("SCALPING","0.3.0", False, direction, int(score), 0.3, True, entry_zone, stop, [tp], [f"scalping {direction} score {score}<{min_score} netR {net_r:.2f} imb {imb:.2f} vp poc {poc:.2f}"], ["INSUFFICIENT_RR"], [tf], view.quality_state(symbol))
    qs = view.quality_state(symbol)
    if qs not in ("HEALTHY","DEGRADED"):
        return StrategyResult("SCALPING","0.3.0", False, direction, int(score), 0.35, True, entry_zone, stop, [tp], [f"quality {qs}"], [qs], [tf], qs)
    return StrategyResult("SCALPING","0.3.0", True, direction, int(score), 0.58, True, entry_zone, stop, [tp], [f"scalping {direction} close {last_close:.2f} poc {poc:.2f} va [{va_low:.2f},{va_high:.2f}] imb {imb:.2f} netR {net_r:.2f} atr {atr:.2f}"], [], [tf], qs)
