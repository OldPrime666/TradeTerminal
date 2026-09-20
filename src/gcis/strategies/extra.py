"""
STR-03/04/05/08 extra strategies P12 — free-only, causal, deterministic.
All use MarketView(as_of) + closed candles only.
"""
from decimal import Decimal
from typing import List, Optional
import pandas as pd
from gcis.strategies.base import StrategyResult
from gcis.market.indicators import ema, rsi_wilder, atr_wilder, bollinger

STRATEGY_VERSION = "0.2.0"

def _safe_atr(high, low, close):
    try:
        atr = atr_wilder(high, low, close, 14)
        v = float(atr.iloc[-1])
        if pd.isna(v) or v <= 0:
            return float(close.iloc[-1]) * 0.005
        return v
    except Exception:
        return float(close.iloc[-1]) * 0.005 if len(close) else 1.0

# STR-03 EMA Cross trend
def evaluate_ema_cross(view, symbol: str, config: dict) -> StrategyResult:
    tf = config.get("analysis_timeframes",{}).get("setup","15m")
    strat_cfg = config.get("strategy",{}).get("ema_cross", {"fast":9,"slow":21,"stop_atr":1.0,"tp_r":2.0})
    fast = strat_cfg.get("fast", 9)
    slow = strat_cfg.get("slow", 21)
    stop_atr = strat_cfg.get("stop_atr", 1.0)
    tp_r = strat_cfg.get("tp_r", 2.0)
    df = view.get_closed_candles(symbol, tf)
    if df.empty or len(df) < max(slow+5, 30):
        return StrategyResult("EMA-CROSS","0.2.0", False, None, 0, 0.0, False, None, None, None, ["INSUFFICIENT_HISTORY"], ["INSUFFICIENT_HISTORY"], [tf], view.quality_state(symbol))
    closes = df["close"].astype(float)
    f = ema(closes, fast)
    s = ema(closes, slow)
    if pd.isna(f.iloc[-1]) or pd.isna(s.iloc[-1]) or pd.isna(f.iloc[-2]) or pd.isna(s.iloc[-2]):
        return StrategyResult("EMA-CROSS","0.2.0", False, None, 10, 0.2, True, None, None, None, ["EMA_NA"], ["NO_CLEAR_ENTRY"], [tf], view.quality_state(symbol))
    # cross detection causal: prev bar cross
    prev_fast = float(f.iloc[-2]); prev_slow = float(s.iloc[-2])
    cur_fast = float(f.iloc[-1]); cur_slow = float(s.iloc[-1])
    atr = _safe_atr(df["high"], df["low"], df["close"])
    last_close = Decimal(str(df.iloc[-1]["close"]))
    direction = None
    if prev_fast <= prev_slow and cur_fast > cur_slow:
        direction = "LONG"
    elif prev_fast >= prev_slow and cur_fast < cur_slow:
        direction = "SHORT"
    if direction is None:
        return StrategyResult("EMA-CROSS","0.2.0", False, None, 25, 0.2, True, None, None, None, [f"ema no cross f{cur_fast:.2f} s{cur_slow:.2f}"], ["NO_CLEAR_ENTRY"], [tf], view.quality_state(symbol))
    # entry zone +/- 0.15 ATR
    entry_low = last_close - Decimal(str(atr*0.15))
    entry_high = last_close + Decimal(str(atr*0.15))
    entry_zone = (entry_low, entry_high)
    if direction == "LONG":
        stop = last_close - Decimal(str(atr*stop_atr))
        if stop >= last_close:
            stop = last_close * Decimal("0.99")
        risk = float(last_close - stop)
        tp = last_close + Decimal(str(risk*tp_r))
    else:
        stop = last_close + Decimal(str(atr*stop_atr))
        if stop <= last_close:
            stop = last_close * Decimal("1.01")
        risk = float(stop - last_close)
        tp = last_close - Decimal(str(risk*tp_r))
    # cost check net RR
    taker = config.get("costs",{}).get("taker_fee_bps",5)
    slip = config.get("costs",{}).get("slippage_bps_base",2)
    total_cost_bps = (taker*2 + slip)/10000
    cost = float(last_close) * total_cost_bps
    net_r = (abs(float(tp-last_close))-cost)/(risk+cost) if risk else 0
    min_rr = strat_cfg.get("min_net_rr", 1.0)
    if net_r < min_rr:
        return StrategyResult("EMA-CROSS","0.2.0", False, direction, 40, 0.3, True, entry_zone, stop, [tp], [f"cross {direction} netR {net_r:.2f} <{min_rr}"], ["INSUFFICIENT_RR"], [tf], view.quality_state(symbol))
    score = 60 + (5 if abs(cur_fast-cur_slow)/atr > 0.5 else 0)
    score = min(85, score)
    qs = view.quality_state(symbol)
    return StrategyResult("EMA-CROSS","0.2.0", True, direction, int(score), 0.55, True, entry_zone, stop, [tp], [f"ema cross {direction} f{cur_fast:.2f} s{cur_slow:.2f} atr{atr:.2f} netR{net_r:.2f}"], [], [tf], qs)

# STR-04 Donchian Breakout
def evaluate_donchian(view, symbol: str, config: dict) -> StrategyResult:
    tf = config.get("analysis_timeframes",{}).get("setup","15m")
    strat_cfg = config.get("strategy",{}).get("donchian", {"lookback":20,"stop_atr":1.0,"tp_r":2.5})
    lookback = strat_cfg.get("lookback", 20)
    stop_atr = strat_cfg.get("stop_atr", 1.0)
    tp_r = strat_cfg.get("tp_r", 2.5)
    df = view.get_closed_candles(symbol, tf)
    if df.empty or len(df) < lookback+5:
        return StrategyResult("DONCHIAN","0.2.0", False, None, 0, 0.0, False, None, None, None, ["INSUFFICIENT_HISTORY"], ["INSUFFICIENT_HISTORY"], [tf], view.quality_state(symbol))
    # donchian from prior lookback bars excluding current
    prev = df.iloc[-(lookback+1):-1]
    ch_high = float(prev["high"].max())
    ch_low = float(prev["low"].min())
    close = float(df.iloc[-1]["close"])
    # breakout condition: close > ch_high => LONG, close < ch_low => SHORT
    direction = None
    if close > ch_high:
        direction = "LONG"
    elif close < ch_low:
        direction = "SHORT"
    if direction is None:
        return StrategyResult("DONCHIAN","0.2.0", False, None, 20, 0.2, True, None, None, None, [f"no breakout close{close:.2f} donH{ch_high:.2f} donL{ch_low:.2f}"], ["NO_CLEAR_ENTRY"], [tf], view.quality_state(symbol))
    last_close = Decimal(str(close))
    atr = _safe_atr(df["high"], df["low"], df["close"])
    entry_zone = (last_close - Decimal(str(atr*0.1)), last_close + Decimal(str(atr*0.1)))
    if direction == "LONG":
        stop = Decimal(str(ch_low)) - Decimal(str(atr*0.2)) if ch_low < float(last_close) else last_close - Decimal(str(atr*stop_atr))
        if stop >= last_close:
            stop = last_close - Decimal(str(atr*stop_atr))
        risk = float(last_close - stop)
        tp = last_close + Decimal(str(risk*tp_r))
    else:
        stop = Decimal(str(ch_high)) + Decimal(str(atr*0.2)) if ch_high > float(last_close) else last_close + Decimal(str(atr*stop_atr))
        if stop <= last_close:
            stop = last_close + Decimal(str(atr*stop_atr))
        risk = float(stop - last_close)
        tp = last_close - Decimal(str(risk*tp_r))
    taker = config.get("costs",{}).get("taker_fee_bps",5)
    slip = config.get("costs",{}).get("slippage_bps_base",2)
    total_cost_bps = (taker*2 + slip)/10000
    cost = float(last_close) * total_cost_bps
    net_r = (abs(float(tp-last_close))-cost)/(risk+cost) if risk else 0
    if net_r < strat_cfg.get("min_net_rr", 1.2):
        return StrategyResult("DONCHIAN","0.2.0", False, direction, 35, 0.3, True, entry_zone, stop, [tp], [f"breakout {direction} netR {net_r:.2f} low"], ["INSUFFICIENT_RR"], [tf], view.quality_state(symbol))
    qs = view.quality_state(symbol)
    score = 62 if direction else 20
    return StrategyResult("DONCHIAN","0.2.0", True, direction, int(score), 0.58, True, entry_zone, stop, [tp], [f"donchian {direction} close{close:.2f} H{ch_high:.2f} L{ch_low:.2f} netR{net_r:.2f}"], [], [tf], qs)

# STR-05 RSI Mean-Reversion
def evaluate_rsi_reversion(view, symbol: str, config: dict) -> StrategyResult:
    tf = config.get("analysis_timeframes",{}).get("setup","15m")
    strat_cfg = config.get("strategy",{}).get("rsi_reversion", {"rsi_period":14,"oversold":30,"overbought":70,"stop_atr":1.2,"tp_r":1.8})
    rsi_period = strat_cfg.get("rsi_period", 14)
    oversold = strat_cfg.get("oversold", 30)
    overbought = strat_cfg.get("overbought", 70)
    stop_atr = strat_cfg.get("stop_atr", 1.2)
    tp_r = strat_cfg.get("tp_r", 1.8)
    df = view.get_closed_candles(symbol, tf)
    if df.empty or len(df) < rsi_period+30:
        return StrategyResult("RSI-REV","0.2.0", False, None, 0, 0.0, False, None, None, None, ["INSUFFICIENT_HISTORY"], ["INSUFFICIENT_HISTORY"], [tf], view.quality_state(symbol))
    rsi = rsi_wilder(df["close"], rsi_period)
    mid, upper, lower, bw = bollinger(df["close"], 20, 2.0)
    if pd.isna(rsi.iloc[-1]) or pd.isna(lower.iloc[-1]) or pd.isna(upper.iloc[-1]):
        return StrategyResult("RSI-REV","0.2.0", False, None, 15, 0.2, True, None, None, None, ["RSI_NA"], ["NO_CLEAR_ENTRY"], [tf], view.quality_state(symbol))
    cur_rsi = float(rsi.iloc[-1])
    cur_close = float(df.iloc[-1]["close"])
    cur_lower = float(lower.iloc[-1])
    cur_upper = float(upper.iloc[-1])
    direction = None
    if cur_rsi < oversold and cur_close <= cur_lower + (cur_upper-cur_lower)*0.05:
        direction = "LONG"
    elif cur_rsi > overbought and cur_close >= cur_upper - (cur_upper-cur_lower)*0.05:
        direction = "SHORT"
    if direction is None:
        return StrategyResult("RSI-REV","0.2.0", False, None, 22, 0.25, True, None, None, None, [f"rsi {cur_rsi:.1f} close {cur_close:.2f} bb [{cur_lower:.2f},{cur_upper:.2f}] no rev"], ["NO_CLEAR_ENTRY"], [tf], view.quality_state(symbol))
    last_close = Decimal(str(cur_close))
    atr = _safe_atr(df["high"], df["low"], df["close"])
    entry_zone = (last_close - Decimal(str(atr*0.2)), last_close + Decimal(str(atr*0.2)))
    if direction == "LONG":
        stop = last_close - Decimal(str(atr*stop_atr))
        risk = float(last_close - stop)
        tp = last_close + Decimal(str(risk*tp_r))
    else:
        stop = last_close + Decimal(str(atr*stop_atr))
        risk = float(stop - last_close)
        tp = last_close - Decimal(str(risk*tp_r))
    taker = config.get("costs",{}).get("taker_fee_bps",5)
    slip = config.get("costs",{}).get("slippage_bps_base",2)
    total_cost_bps = (taker*2 + slip)/10000
    cost = float(last_close) * total_cost_bps
    net_r = (abs(float(tp-last_close))-cost)/(risk+cost) if risk else 0
    if net_r < 1.0:
        return StrategyResult("RSI-REV","0.2.0", False, direction, 32, 0.3, True, entry_zone, stop, [tp], [f"rsi rev {direction} netR {net_r:.2f}"], ["INSUFFICIENT_RR"], [tf], view.quality_state(symbol))
    qs = view.quality_state(symbol)
    return StrategyResult("RSI-REV","0.2.0", True, direction, 58, 0.52, True, entry_zone, stop, [tp], [f"rsi rev {direction} rsi{cur_rsi:.1f} bb[{cur_lower:.2f},{cur_upper:.2f}] netR{net_r:.2f}"], [], [tf], qs)

# STR-08 Confluence (ICT-A + EMA filter)
def evaluate_confluence(view, symbol: str, config: dict) -> StrategyResult:
    # import inside to avoid circular
    from gcis.strategies.ict_a import evaluate_ict_a
    tf = config.get("analysis_timeframes",{}).get("setup","15m")
    # get both signals
    ict_res = evaluate_ict_a(view, symbol, config)
    ema_res = evaluate_ema_cross(view, symbol, config)
    # Confluence requires both eligible same direction
    if not ict_res.eligible:
        return StrategyResult("CONFLUENCE","0.2.0", False, ict_res.direction, max(10,ict_res.setup_score-10), 0.25, ict_res.regime_compatibility, ict_res.entry_zone, ict_res.invalidation, ict_res.targets, ict_res.evidence+["confluence: ICT not eligible"], ["NO_CLEAR_ENTRY"], [tf], view.quality_state(symbol))
    if not ema_res.eligible:
        return StrategyResult("CONFLUENCE","0.2.0", False, ict_res.direction, max(15,ict_res.setup_score-5), 0.3, ict_res.regime_compatibility, ict_res.entry_zone, ict_res.invalidation, ict_res.targets, ict_res.evidence+[f"confluence: EMA not eligible {ema_res.reason_codes}"], ["NO_CLEAR_ENTRY"], [tf], view.quality_state(symbol))
    if ict_res.direction != ema_res.direction:
        return StrategyResult("CONFLUENCE","0.2.0", False, ict_res.direction, 35, 0.3, True, ict_res.entry_zone, ict_res.invalidation, ict_res.targets, ict_res.evidence+ema_res.evidence+["confluence direction mismatch"], ["MARKET_REGIME_INCOMPATIBLE"], [tf], view.quality_state(symbol))
    # both agree => boost score
    boosted = min(95, ict_res.setup_score + 10 + (ema_res.setup_score//5))
    combined_evidence = ict_res.evidence + ema_res.evidence + [f"confluence {ict_res.direction} boosted {ict_res.setup_score}->{boosted}"]
    qs = view.quality_state(symbol)
    # use ICT entry/stop/target but boosted confidence
    return StrategyResult("CONFLUENCE","0.2.0", True, ict_res.direction, int(boosted), 0.72, True, ict_res.entry_zone, ict_res.invalidation, ict_res.targets, combined_evidence, [], [tf], qs)
