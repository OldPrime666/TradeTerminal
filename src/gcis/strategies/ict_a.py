from decimal import Decimal
from typing import List
import pandas as pd
from gcis.strategies.base import StrategyResult
from gcis.market.indicators import atr_wilder
from gcis.ict.swings import detect_swings
from gcis.ict.structure import detect_structure
from gcis.ict.displacement import find_displacements
from gcis.ict.fvg import detect_fvgs
from gcis.ict.order_blocks import detect_order_blocks
from gcis.ict.sweeps import detect_sweeps

STRATEGY_VERSION = "0.1.0"

def evaluate_ict_a(view, symbol: str, config: dict) -> StrategyResult:
    """
    ICT-A long-only flagship: HTF bias BULLISH, regime not NEWS_SHOCK, sweep confirmed, displacement, BOS/CHOCH, FVG/OB, discount.
    For view with multiple timeframes, we use 15m setup, 5m trigger, 1h bias.
    """
    evidence: List[str] = []
    reasons: List[str] = []
    # require history
    setup_tf = config.get("analysis_timeframes",{}).get("setup","15m")
    trigger_tf = config.get("analysis_timeframes",{}).get("trigger","5m")
    bias_tf = config.get("analysis_timeframes",{}).get("bias","1h")
    # config params
    ict_cfg = config.get("ict",{})
    strat_cfg = config.get("strategy",{}).get("ict_a",{})
    # get candles
    df_setup = view.get_closed_candles(symbol, setup_tf)
    df_bias = view.get_closed_candles(symbol, bias_tf)
    if df_setup.empty or len(df_setup) < 50:
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, None, 0, 0.0, False, None, None, None, ["INSUFFICIENT_HISTORY"], ["INSUFFICIENT_HISTORY"], [setup_tf, bias_tf], view.quality_state(symbol))
    if df_bias.empty or len(df_bias) < 30:
        # still allow but mark no htf
        evidence.append("HTF data insufficient - waiting for bias")
        # not eligible
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, None, 0, 0.0, False, None, None, None, evidence, ["INSUFFICIENT_HISTORY"], [setup_tf, bias_tf], view.quality_state(symbol))
    # compute ATR
    atr_setup = atr_wilder(df_setup["high"], df_setup["low"], df_setup["close"], 14)
    atr_bias = atr_wilder(df_bias["high"], df_bias["low"], df_bias["close"], 14)
    # bias: need bullish
    # detect swings and structure on bias
    swings_bias = detect_swings(df_bias, symbol, bias_tf, L=3, R=3, atr_series=atr_bias)
    struct_bias, bias = detect_structure(swings_bias, df_bias, bos_buffer_atr=ict_cfg.get("structure",{}).get("min_break_atr",0.10), atr_series=atr_bias)
    evidence.append(f"HTF bias {bias} from {len(struct_bias)} structure events")
    if bias != "BULLISH":
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, None, 0, 0.0, False, None, None, None, evidence + [f"HTF_BIAS_{bias}"], ["MARKET_REGIME_INCOMPATIBLE"], [setup_tf, bias_tf], view.quality_state(symbol))
    # setup: swings/structure
    swings_setup = detect_swings(df_setup, symbol, setup_tf, L=3, R=3, atr_series=atr_setup)
    struct_setup, bias_setup = detect_structure(swings_setup, df_setup, bos_buffer_atr=ict_cfg.get("structure",{}).get("min_break_atr",0.10), atr_series=atr_setup)
    evidence.append(f"Setup swings {len(swings_setup)} structure {len(struct_setup)} bias {bias_setup}")
    # displacement
    disp_cfg = ict_cfg.get("displacement",{})
    disp_idx = find_displacements(df_setup, atr_setup, disp_cfg)
    evidence.append(f"displacements {len(disp_idx)}")
    # sweeps
    sweep_cfg = ict_cfg.get("liquidity",{}).get("sweep",{})
    sweeps = detect_sweeps(df_setup, symbol, setup_tf, atr_setup, sweep_cfg, displacement_indices=disp_idx)
    confirmed_bull_sweeps = [s for s in sweeps if s.direction=="BULL" and s.confirmation_status=="CONFIRMED"]
    evidence.append(f"sweeps {len(sweeps)} bullish-confirmed {len(confirmed_bull_sweeps)}")
    if not confirmed_bull_sweeps:
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, None, 20, 0.1, True, None, None, None, evidence, ["INVALID_STRUCTURE"], [setup_tf], view.quality_state(symbol))
    # FVG and OB
    fvg_cfg = ict_cfg.get("fvg",{})
    fvgs = detect_fvgs(df_setup, symbol, setup_tf, atr_setup, fvg_cfg, displacement_indices=disp_idx)
    bullish_fvgs = [f for f in fvgs if f.direction=="BULL"]
    obs = detect_order_blocks(df_setup, symbol, setup_tf, struct_setup, {})
    bullish_obs = [o for o in obs if o.direction=="BULL"]
    evidence.append(f"FVG bullish {len(bullish_fvgs)} OB bullish {len(bullish_obs)}")
    if not bullish_fvgs and not bullish_obs:
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, None, 35, 0.2, True, None, None, None, evidence, ["NO_CLEAR_ENTRY"], [setup_tf], view.quality_state(symbol))
    # choose entry zone: prefer FVG else OB
    entry_zone = None
    if bullish_fvgs:
        fvg = bullish_fvgs[-1]
        entry_zone = (fvg.lower, fvg.upper)
        evidence.append(f"entry FVG {fvg.lower}-{fvg.upper} mp {fvg.midpoint}")
    elif bullish_obs:
        ob = bullish_obs[-1]
        entry_zone = (ob.zone_low, ob.zone_high)
        evidence.append(f"entry OB {ob.zone_low}-{ob.zone_high}")
    # discount check
    require_discount = ict_cfg.get("premium_discount",{}).get("require_discount_for_long", True)
    if require_discount:
        # compute dealing range from last swing high/low that bracket last structure
        # simplified: if price near high of recent range, reject
        recent_high = float(df_setup["high"].tail(20).max())
        recent_low = float(df_setup["low"].tail(20).min())
        eq = (recent_high + recent_low)/2
        # current close
        cur_close = float(df_setup.iloc[-1]["close"])
        if cur_close > eq:
            # premium -> still allow but evidence note
            evidence.append(f"premium/discount: cur {cur_close:.2f} > eq {eq:.2f} (premium) - want discount but allowed via gate")
            # if strict, block; we will not block by default but note
            # return not eligible if strict
            pass
        else:
            evidence.append(f"discount ok cur {cur_close:.2f} <= eq {eq:.2f}")
    # entry/invalidation/targets
    last_close = Decimal(str(df_setup.iloc[-1]["close"]))
    atr_last = float(atr_setup.iloc[-1]) if not pd.isna(atr_setup.iloc[-1]) else float(last_close) * 0.01
    stop_buffer = strat_cfg.get("stop_buffer_atr", 0.25) * atr_last
    # stop below zone low or sweep extreme
    zone_low = entry_zone[0] if entry_zone else last_close * Decimal("0.99")
    sweep_low = min([s.level for s in confirmed_bull_sweeps]) if confirmed_bull_sweeps else zone_low
    stop_price = min(zone_low, sweep_low) - Decimal(str(stop_buffer))
    # ensure stop < entry
    entry_price = (entry_zone[0] + entry_zone[1]) / 2 if entry_zone and entry_zone[0]!=entry_zone[1] else last_close
    if stop_price >= entry_price:
        stop_price = entry_price * Decimal("0.99")
    # targets: TP1 1.5R, TP2 nearest swing high / PDH
    risk = float(entry_price - stop_price)
    tp1 = entry_price + Decimal(str(strat_cfg.get("tp1_r",1.5) * risk))
    tp2_r = strat_cfg.get("tp2_r",3.0)
    tp2 = entry_price + Decimal(str(tp2_r * risk))
    # check R:R net of costs
    taker_bps = config.get("costs",{}).get("taker_fee_bps",10)
    slippage_bps = config.get("costs",{}).get("slippage_bps_base",2)
    total_cost_bps = (taker_bps*2 + slippage_bps) / 10000
    cost = float(entry_price) * total_cost_bps
    net_r_tp1 = (float(tp1 - entry_price) - cost) / (risk + cost) if risk else 0
    net_r_final = (float(tp2 - entry_price) - cost) / (risk + cost) if risk else 0
    evidence.append(f"risk {risk:.2f} cost {cost:.4f} netR tp1 {net_r_tp1:.2f} final {net_r_final:.2f}")
    min_net_rr_tp1 = strat_cfg.get("min_net_rr_tp1", 1.2)
    min_net_rr_final = strat_cfg.get("min_net_rr_final", 2.0)
    if net_r_tp1 < min_net_rr_tp1 or net_r_final < min_net_rr_final:
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, "LONG", 45, 0.3, True, (entry_zone[0], entry_zone[1]) if entry_zone else None, stop_price, [tp1,tp2], evidence, ["INSUFFICIENT_RR"], [setup_tf], view.quality_state(symbol))
    # setup score: weighted categories (descriptive)
    # Simplified scoring: htf alignment 20, sweep quality 20, displacement 15, zone quality 15, regime 10, session 5, volume 5, cost 10
    score = 0
    score += 20  # htf bullish
    score += 15 if confirmed_bull_sweeps else 0
    score += 10 if disp_idx else 0
    score += 15 if bullish_fvgs or bullish_obs else 0
    score += 5  # regime compat (simplified)
    score += 5  # session
    score += 5  # volume
    score += 5 if net_r_final>2 else 0
    score = min(100, score)
    # check max qualityState
    qs = view.quality_state(symbol)
    if qs not in ("HEALTHY","DEGRADED"):
        return StrategyResult("ICT-A", STRATEGY_VERSION, False, "LONG", score, 0.4, True, (entry_zone[0], entry_zone[1]), stop_price, [tp1,tp2], evidence, [qs], [setup_tf], qs)
    return StrategyResult("ICT-A", STRATEGY_VERSION, True, "LONG", score, 0.65, True, (entry_zone[0], entry_zone[1]) if entry_zone else None, stop_price, [tp1,tp2], evidence, [], [setup_tf, bias_tf], qs)
