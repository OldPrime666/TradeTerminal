from decimal import Decimal
from typing import List, Optional
import pandas as pd
from gcis.strategies.base import StrategyResult
from gcis.market.indicators import atr_wilder
from gcis.ict.swings import detect_swings
from gcis.ict.structure import detect_structure
from gcis.ict.displacement import find_displacements
from gcis.ict.fvg import detect_fvgs
from gcis.ict.order_blocks import detect_order_blocks
from gcis.ict.sweeps import detect_sweeps
from gcis.ict.premium import is_discount, is_premium, compute_dealing_range

STRATEGY_VERSION = "0.1.0"

def _evaluate_direction(view, symbol: str, config: dict, direction: str, df_setup: pd.DataFrame, df_bias, atr_setup, atr_bias, ict_cfg, strat_cfg):
    """
    Helper for single direction. Returns StrategyResult (may be ineligible).
    direction: LONG or SHORT
    """
    evidence: List[str] = []
    setup_tf = config.get("analysis_timeframes",{}).get("setup","15m")
    bias_tf = config.get("analysis_timeframes",{}).get("bias","1h")
    # HTF bias check
    swings_bias = detect_swings(df_bias, symbol, bias_tf, L=3, R=3, atr_series=atr_bias)
    struct_bias, bias = detect_structure(swings_bias, df_bias, bos_buffer_atr=ict_cfg.get("structure",{}).get("min_break_atr",0.10), atr_series=atr_bias)
    evidence.append(f"HTF bias {bias} from {len(struct_bias)} structure events")
    # direction-specific bias requirement
    if direction == "LONG" and bias != "BULLISH":
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, None, 0, 0.0, False, None, None, None, evidence + [f"HTF_BIAS_{bias}_NEED_BULL"], ["MARKET_REGIME_INCOMPATIBLE"], [setup_tf, bias_tf], view.quality_state(symbol))
    if direction == "SHORT" and bias != "BEARISH":
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, None, 0, 0.0, False, None, None, None, evidence + [f"HTF_BIAS_{bias}_NEED_BEAR"], ["MARKET_REGIME_INCOMPATIBLE"], [setup_tf, bias_tf], view.quality_state(symbol))
    # setup swings/structure
    swings_setup = detect_swings(df_setup, symbol, setup_tf, L=3, R=3, atr_series=atr_setup)
    struct_setup, bias_setup = detect_structure(swings_setup, df_setup, bos_buffer_atr=ict_cfg.get("structure",{}).get("min_break_atr",0.10), atr_series=atr_setup)
    evidence.append(f"Setup swings {len(swings_setup)} structure {len(struct_setup)} bias {bias_setup}")
    disp_cfg = ict_cfg.get("displacement",{})
    disp_idx = find_displacements(df_setup, atr_setup, disp_cfg)
    evidence.append(f"displacements {len(disp_idx)}")
    sweep_cfg = ict_cfg.get("liquidity",{}).get("sweep",{}) or ict_cfg.get("liquidity",{})
    # sweep_cfg may be nested; ensure we pass outer for equal levels
    liquidity_cfg = ict_cfg.get("liquidity",{})
    sweeps = detect_sweeps(df_setup, symbol, setup_tf, atr_setup, liquidity_cfg if liquidity_cfg else sweep_cfg, displacement_indices=disp_idx)
    if direction == "LONG":
        confirmed = [s for s in sweeps if s.direction=="BULL" and s.confirmation_status=="CONFIRMED"]
        evidence.append(f"sweeps {len(sweeps)} bullish-confirmed {len(confirmed)}")
        if not confirmed:
            return StrategyResult("ICT-A", STRATEGY_VERSION, False, None, 20, 0.1, True, None, None, None, evidence, ["INVALID_STRUCTURE"], [setup_tf], view.quality_state(symbol))
    else:
        confirmed = [s for s in sweeps if s.direction=="BEAR" and s.confirmation_status=="CONFIRMED"]
        evidence.append(f"sweeps {len(sweeps)} bearish-confirmed {len(confirmed)}")
        if not confirmed:
            return StrategyResult("ICT-A", STRATEGY_VERSION, False, None, 20, 0.1, True, None, None, None, evidence, ["INVALID_STRUCTURE"], [setup_tf], view.quality_state(symbol))
    # FVG and OB
    fvg_cfg = ict_cfg.get("fvg",{})
    fvgs = detect_fvgs(df_setup, symbol, setup_tf, atr_setup, fvg_cfg, displacement_indices=disp_idx)
    obs = detect_order_blocks(df_setup, symbol, setup_tf, struct_setup, ict_cfg.get("order_block",{}), atr_series=atr_setup, displacement_indices=disp_idx)
    if direction == "LONG":
        zone_candidates = [f for f in fvgs if f.direction=="BULL"]
        obs_candidates = [o for o in obs if o.direction=="BULL"]
        evidence.append(f"FVG bullish {len(zone_candidates)} OB bullish {len(obs_candidates)}")
    else:
        zone_candidates = [f for f in fvgs if f.direction=="BEAR"]
        obs_candidates = [o for o in obs if o.direction=="BEAR"]
        evidence.append(f"FVG bearish {len(zone_candidates)} OB bearish {len(obs_candidates)}")
    if not zone_candidates and not obs_candidates:
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, None, 35, 0.2, True, None, None, None, evidence, ["NO_CLEAR_ENTRY"], [setup_tf], view.quality_state(symbol))
    entry_zone = None
    if zone_candidates:
        fvg = zone_candidates[-1]
        entry_zone = (fvg.lower, fvg.upper)
        evidence.append(f"entry FVG {fvg.lower}-{fvg.upper} mp {fvg.midpoint}")
    else:
        ob = obs_candidates[-1]
        entry_zone = (ob.zone_low, ob.zone_high)
        evidence.append(f"entry OB {ob.zone_low}-{ob.zone_high}")
    # premium/discount check per direction strict
    low, high = compute_dealing_range(df_setup, lookback=20)
    cur_close = float(df_setup.iloc[-1]["close"])
    premium_cfg = ict_cfg.get("premium_discount",{})
    if direction == "LONG":
        require_discount = premium_cfg.get("require_discount_for_long", True)
        if require_discount and not is_discount(cur_close, low, high):
            evidence.append(f"premium/discount: cur {cur_close:.2f} > eq {(low+high)/2:.2f} premium block")
            return StrategyResult("ICT-A", STRATEGY_VERSION, False, "LONG", 45, 0.3, True, entry_zone, None, None, evidence, ["MARKET_REGIME_INCOMPATIBLE"], [setup_tf], view.quality_state(symbol))
        else:
            evidence.append(f"discount ok cur {cur_close:.2f} <= eq {(low+high)/2:.2f}" if require_discount else "discount not required")
    else:
        require_premium = premium_cfg.get("require_premium_for_short", True)
        if require_premium and not is_premium(cur_close, low, high):
            evidence.append(f"premium/discount: cur {cur_close:.2f} < eq {(low+high)/2:.2f} discount block for short")
            return StrategyResult("ICT-A", STRATEGY_VERSION, False, "SHORT", 45, 0.3, True, entry_zone, None, None, evidence, ["MARKET_REGIME_INCOMPATIBLE"], [setup_tf], view.quality_state(symbol))
        else:
            evidence.append(f"premium ok cur {cur_close:.2f} >= eq {(low+high)/2:.2f}" if require_premium else "premium not required")
    # entry/stop/targets
    last_close = Decimal(str(df_setup.iloc[-1]["close"]))
    atr_last = float(atr_setup.iloc[-1]) if not pd.isna(atr_setup.iloc[-1]) else float(last_close) * 0.01
    stop_buffer = strat_cfg.get("stop_buffer_atr", 0.25) * atr_last
    if direction == "LONG":
        zone_low = entry_zone[0]
        sweep_level = min([s.level for s in confirmed]) if confirmed else zone_low
        stop_price = min(zone_low, sweep_level) - Decimal(str(stop_buffer))
        entry_price = (entry_zone[0] + entry_zone[1]) / 2 if entry_zone and entry_zone[0]!=entry_zone[1] else last_close
        if stop_price >= entry_price:
            stop_price = entry_price * Decimal("0.99")
        risk = float(entry_price - stop_price)
        tp1 = entry_price + Decimal(str(strat_cfg.get("tp1_r",1.5) * risk))
        tp2 = entry_price + Decimal(str(strat_cfg.get("tp2_r",3.0) * risk))
    else:
        zone_high = entry_zone[1]
        sweep_level = max([s.level for s in confirmed]) if confirmed else zone_high
        stop_price = max(zone_high, sweep_level) + Decimal(str(stop_buffer))
        entry_price = (entry_zone[0] + entry_zone[1]) / 2 if entry_zone and entry_zone[0]!=entry_zone[1] else last_close
        if stop_price <= entry_price:
            stop_price = entry_price * Decimal("1.01")
        risk = float(stop_price - entry_price)
        tp1 = entry_price - Decimal(str(strat_cfg.get("tp1_r",1.5) * risk))
        tp2 = entry_price - Decimal(str(strat_cfg.get("tp2_r",3.0) * risk))
    # cost check net R
    taker_bps = config.get("costs",{}).get("taker_fee_bps",5)
    slippage_bps = config.get("costs",{}).get("slippage_bps_base",2)
    total_cost_bps = (taker_bps*2 + slippage_bps) / 10000
    cost = float(entry_price) * total_cost_bps
    if direction == "LONG":
        net_r_tp1 = (float(tp1 - entry_price) - cost) / (risk + cost) if risk else 0
        net_r_final = (float(tp2 - entry_price) - cost) / (risk + cost) if risk else 0
    else:
        net_r_tp1 = (float(entry_price - tp1) - cost) / (risk + cost) if risk else 0
        net_r_final = (float(entry_price - tp2) - cost) / (risk + cost) if risk else 0
    evidence.append(f"risk {risk:.2f} cost {cost:.4f} netR tp1 {net_r_tp1:.2f} final {net_r_final:.2f}")
    min_net_rr_tp1 = strat_cfg.get("min_net_rr_tp1", 1.2)
    min_net_rr_final = strat_cfg.get("min_net_rr_final", 2.0)
    if net_r_tp1 < min_net_rr_tp1 or net_r_final < min_net_rr_final:
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, direction, 45, 0.3, True, entry_zone, stop_price, [tp1,tp2], evidence, ["INSUFFICIENT_RR"], [setup_tf], view.quality_state(symbol))
    # setup score weighted (simplified but uses fusion weights via compute)
    # We compute score here as well for backward compat, but fusion will recompute
    score = 0
    score += 20  # htf
    score += 15 if confirmed else 0
    score += 10 if disp_idx else 0
    score += 15 if zone_candidates or obs_candidates else 0
    score += 5
    score += 5
    score += 5
    score += 5 if net_r_final>2 else 0
    score = min(100, score)
    qs = view.quality_state(symbol)
    if qs not in ("HEALTHY","DEGRADED"):
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, direction, score, 0.4, True, entry_zone, stop_price, [tp1,tp2], evidence, [qs], [setup_tf], qs)
    return StrategyResult("ICT-A", STRATEGY_VERSION, True, direction, score, 0.65, True, entry_zone, stop_price, [tp1,tp2], evidence, [], [setup_tf, bias_tf], qs)


def evaluate_ict_a(view, symbol: str, config: dict) -> StrategyResult:
    """
    ICT-A bi-directional: evaluates both LONG and SHORT and returns best eligible.
    If both eligible, picks higher setup_score; if none eligible, returns most promising ineligible (higher score) with reasons.
    Config strategy.ict_a.directions controls allowed (default [LONG,SHORT]).
    """
    setup_tf = config.get("analysis_timeframes",{}).get("setup","15m")
    bias_tf = config.get("analysis_timeframes",{}).get("bias","1h")
    strat_cfg = config.get("strategy",{}).get("ict_a",{})
    allowed_dirs = strat_cfg.get("directions", ["LONG","SHORT"])
    # get DataFrames once
    df_setup = view.get_closed_candles(symbol, setup_tf)
    df_bias = view.get_closed_candles(symbol, bias_tf)
    if df_setup.empty or len(df_setup) < 50:
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, None, 0, 0.0, False, None, None, None, ["INSUFFICIENT_HISTORY"], ["INSUFFICIENT_HISTORY"], [setup_tf, bias_tf], view.quality_state(symbol))
    if df_bias.empty or len(df_bias) < 30:
        evidence = ["HTF data insufficient - waiting for bias"]
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, None, 0, 0.0, False, None, None, None, evidence, ["INSUFFICIENT_HISTORY"], [setup_tf, bias_tf], view.quality_state(symbol))
    atr_setup = atr_wilder(df_setup["high"], df_setup["low"], df_setup["close"], 14)
    atr_bias = atr_wilder(df_bias["high"], df_bias["low"], df_bias["close"], 14)
    ict_cfg = config.get("ict",{})
    results = []
    for direction in allowed_dirs:
        # Use helper
        # Need to handle that helper already computes df etc, but we pass precomputed to avoid duplicate
        res = _evaluate_direction(view, symbol, config, direction, df_setup, df_bias, atr_setup, atr_bias, ict_cfg, strat_cfg)
        results.append(res)
    # Prefer eligible with higher score
    eligible = [r for r in results if r.eligible]
    if eligible:
        best = max(eligible, key=lambda x: x.setup_score)
        return best
    # none eligible -> return highest score ineligible for gate display
    # choose the one with highest score (most promising)
    best = max(results, key=lambda x: x.setup_score if x.setup_score is not None else -1)
    return best
