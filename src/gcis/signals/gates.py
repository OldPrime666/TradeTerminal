from typing import List
from gcis.core.enums import GateReason

# Two gate groups: MV (market validity) and PX (portfolio/execution)

MV_GATES = [
    GateReason.DATA_STALE,
    GateReason.DATA_DISCONNECTED,
    GateReason.CANDLE_DATA_INVALID,
    GateReason.CLOCK_DRIFT,
    GateReason.MARKET_DATA_DISCREPANCY,
    GateReason.INSUFFICIENT_HISTORY,
    GateReason.SYMBOL_INVALID,
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
]

PX_GATES = [
    GateReason.RISK_LIMIT,
    GateReason.COOLDOWN_ACTIVE,
    GateReason.DUPLICATE_SETUP,
    GateReason.KILL_SWITCH_ACTIVE,
    GateReason.RECONCILIATION_ERROR,
    GateReason.EXECUTION_UNSAFE,
    GateReason.INSUFFICIENT_PROBABILITY_DATA,
]

def evaluate_mv_gates(strategy_result, view, symbol: str, config: dict) -> List[str]:
    reasons=[]
    # data stale/disconnected
    qs = view.quality_state(symbol)
    if qs == "DISCONNECTED":
        reasons.append(GateReason.DATA_DISCONNECTED.value)
    elif qs == "DEGRADED":
        # allow but not block unless stale?
        pass
    # strategy eligibility already encodes many
    if not strategy_result.eligible:
        for rc in strategy_result.reason_codes:
            if rc in [r.value for r in MV_GATES] or rc in MV_GATES:
                reasons.append(rc)
            else:
                # map generic
                reasons.append(rc)
        # ensure at least one reason
        if not reasons:
            reasons.append(GateReason.INVALID_STRUCTURE.value)
    # cost gate
    # check if strategy already flagged INSUFFICIENT_RR etc
    return list(set(reasons))

def evaluate_px_gates(signal, risk_state: dict, kill_switch: bool, duplicate: bool) -> List[str]:
    reasons=[]
    if kill_switch:
        reasons.append(GateReason.KILL_SWITCH_ACTIVE.value)
    if risk_state.get("risk_lock") == "BLOCK_NEW_TRADES":
        reasons.append(GateReason.RISK_LIMIT.value)
    if duplicate:
        reasons.append(GateReason.DUPLICATE_SETUP.value)
    if risk_state.get("cooldown_active"):
        reasons.append(GateReason.COOLDOWN_ACTIVE.value)
    # probability gate (handled separately in PRB-12)
    return reasons
