"""
Fidelity & intrabar pessimism BKT-02.

Fidelity levels:
 - OHLC_APPROXIMATION: only OHLC per bar available, pessimistic assume worst.
 - TICK_FROM_BAR: if tick data available (not in P0), could use higher fidelity (stub).

Same-bar TP/SL policy: stop_first (pessimistic) per backtest.same_bar_tp_sl_policy.
"""
from decimal import Decimal

FIDELITY_LEVELS = ["OHLC_APPROXIMATION", "TICK_FROM_BAR"]
DEFAULT_FIDELITY = "OHLC_APPROXIMATION"

def resolve_exit_pessimistic(bar_high: float | Decimal, bar_low: float | Decimal,
                             stop: float | Decimal, target: float | Decimal,
                             direction: str, policy: str = "stop_first") -> str | None:
    """
    Pessimistic intrabar: if both stop and target inside bar's range, assume stop first.
    direction LONG: stop < entry < target ; bar_low <= stop => stop hit, bar_high >= target => target hit.
    direction SHORT: target < entry < stop? Actually short stop above, target below.
    Returns "STOP" | "TARGET" | None.
    Deterministic, no random (jitter allowed but not needed).
    """
    # Normalize to float for comparison, but keep Decimal accuracy if given
    bh = float(bar_high)
    bl = float(bar_low)
    s = float(stop) if stop is not None else None
    t = float(target) if target is not None else None
    if direction == "LONG":
        hit_stop = s is not None and bl <= s
        hit_target = t is not None and bh >= t
    else:  # SHORT
        hit_stop = s is not None and bh >= s
        hit_target = t is not None and bl <= t
    if hit_stop and hit_target:
        # pessimistic
        if policy == "stop_first":
            return "STOP"
        return "STOP"  # default pessimistic
    if hit_stop:
        return "STOP"
    if hit_target:
        return "TARGET"
    return None

def fidelity_for_available_data(has_tick: bool = False) -> str:
    return "TICK_FROM_BAR" if has_tick else "OHLC_APPROXIMATION"

def is_pessimistic(policy: str) -> bool:
    return policy == "stop_first"
