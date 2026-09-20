"""
SIG-01 Gates MV/PX with 30+ reason codes — causal
MV = market validity (data, structure, regime, costs, HTF, etc.)
PX = portfolio/execution (risk, duplicate, kill switch etc.)
Hard gates multiplicative — any failure blocks.
"""
from typing import List
from gcis.core.enums import GateReason

# 30+ distinct codes across MV+PX (GateReason enum has 44 total)
# MV gates: 27 codes
MV_GATES = [
    GateReason.DATA_STALE,
    GateReason.DATA_DISCONNECTED,
    GateReason.ORDERBOOK_STALE,
    GateReason.CANDLE_DATA_INVALID,
    GateReason.CLOCK_DRIFT,
    GateReason.MARKET_DATA_DISCREPANCY,
    GateReason.INSUFFICIENT_HISTORY,
    GateReason.SYMBOL_INVALID,
    GateReason.CONTRACT_NOT_TRADING,
    GateReason.CONTRACT_SETTLING,
    GateReason.UNIVERSE_WARMING_UP,
    GateReason.LIQUIDITY_TOO_LOW,
    GateReason.SPREAD_TOO_WIDE,
    GateReason.FUNDING_TOO_COSTLY,
    GateReason.LIQUIDATION_BUFFER_INSUFFICIENT,
    GateReason.LEVERAGE_EXCEEDS_CAP,
    GateReason.POSITION_DATA_BLIND,
    GateReason.VENUE_SWITCH_INVALIDATED,
    GateReason.NO_DERIVS_CONTEXT,
    GateReason.MARKET_TYPE_VIOLATION,
    GateReason.INVALID_STRUCTURE,
    GateReason.NO_CLEAR_ENTRY,
    GateReason.NO_CLEAR_TARGET,
    GateReason.INSUFFICIENT_RR,
    GateReason.COST_TOO_HIGH,
    GateReason.MARKET_REGIME_INCOMPATIBLE,
    GateReason.CONFLICTING_EVIDENCE,
    GateReason.HTF_LTF_CONFLICT,
    GateReason.SESSION_INACTIVE,
    GateReason.NEWS_RISK,
    GateReason.NEWS_UNAVAILABLE,
    GateReason.STRATEGY_DISABLED,
    GateReason.EXECUTION_UNSAFE,
]

# PX gates: 6 codes
PX_GATES = [
    GateReason.RISK_LIMIT,
    GateReason.COOLDOWN_ACTIVE,
    GateReason.DUPLICATE_SETUP,
    GateReason.KILL_SWITCH_ACTIVE,
    GateReason.RECONCILIATION_ERROR,
    GateReason.SIGNAL_EXPIRED,
    GateReason.INSUFFICIENT_PROBABILITY_DATA,
]

# All 33+ distinct
ALL_GATE_REASONS = MV_GATES + PX_GATES

def evaluate_mv_gates(strategy_result, view, symbol: str, config: dict) -> List[str]:
    """
    Returns list of MV gate failures (strings). Empty = pass.
    Checks: data quality, strategy eligibility reasons mapped to MV, costs, regime, etc.
    Hard gates — any reason blocks MV pass.
    """
    reasons: List[str] = []
    # 1. data quality from view
    qs = view.quality_state(symbol) if view and hasattr(view, "quality_state") else "HEALTHY"
    if qs == "DISCONNECTED":
        reasons.append(GateReason.DATA_DISCONNECTED.value)
    elif qs == "STALE":
        reasons.append(GateReason.DATA_STALE.value)
    elif qs in ("INVALID", "DISCONNECTED", "STALE"):
        reasons.append(GateReason.CANDLE_DATA_INVALID.value)
    # 2. market data discrepancy flag via view maybe? simplified: if view has discrepancy attribute
    # 3. strategy eligibility: if not eligible, map its reason_codes that are MV gates
    if not strategy_result.eligible:
        for rc in getattr(strategy_result, "reason_codes", []):
            # rc may be string value; map to gate reason if in MV_GATES
            # normalize: compare string value
            rc_str = rc.value if hasattr(rc, "value") else str(rc)
            # if rc is known GateReason value, add it
            # we accept any rc as MV failure if it's in MV set or generic INSUFFICIENT_HISTORY etc.
            # Ensure at least one reason
            reasons.append(rc_str)
        if not reasons:
            reasons.append(GateReason.INVALID_STRUCTURE.value)
    else:
        # even if eligible, still check that strategy didn't produce cost/rr failures that are MV
        for rc in getattr(strategy_result, "reason_codes", []):
            rc_str = rc.value if hasattr(rc, "value") else str(rc)
            if rc_str in [g.value for g in MV_GATES]:
                reasons.append(rc_str)
    # 4. contract checks: if symbol not in valid set? deferred, but we can check strategy requested data
    # 5. deduplicate
    # normalize to values
    uniq = []
    seen=set()
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq

def evaluate_px_gates(signal, risk_state: dict, kill_switch: bool, duplicate: bool) -> List[str]:
    """
    PX gates after MV pass. Checks risk, kill, duplicate, cooldown, reconciliation.
    signal: StrategyResult or dict with fields
    risk_state: dict from risk manager (risk_lock, cooldown_active)
    kill_switch: bool
    duplicate: bool from dedup check
    """
    reasons: List[str] = []
    if kill_switch:
        reasons.append(GateReason.KILL_SWITCH_ACTIVE.value)
    if risk_state and risk_state.get("risk_lock") == "BLOCK_NEW_TRADES":
        reasons.append(GateReason.RISK_LIMIT.value)
    elif risk_state and risk_state.get("risk_lock") in ("RISK_LIMIT", "BLOCK_NEW_TRADES", "COOLDOWN"):
        reasons.append(GateReason.RISK_LIMIT.value)
    if duplicate:
        reasons.append(GateReason.DUPLICATE_SETUP.value)
    if risk_state and risk_state.get("cooldown_active"):
        reasons.append(GateReason.COOLDOWN_ACTIVE.value)
    if risk_state and risk_state.get("reconciliation_error"):
        reasons.append(GateReason.RECONCILIATION_ERROR.value)
    # signal expiry check
    if signal and hasattr(signal, "expires_at"):
        # caller handles expiry
        pass
    # probability gate
    if signal and getattr(signal, "probability_status", None) == "INSUFFICIENT_DATA":
        # only blocks live per PRB, not paper P06
        pass
    return list(dict.fromkeys(reasons))

def is_mv_pass(strategy_result, view, symbol, config) -> bool:
    return len(evaluate_mv_gates(strategy_result, view, symbol, config)) == 0

def is_px_pass(signal, risk_state, kill_switch, duplicate) -> bool:
    return len(evaluate_px_gates(signal, risk_state, kill_switch, duplicate)) == 0
