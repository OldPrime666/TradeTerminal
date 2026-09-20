from datetime import datetime, timedelta, timezone
from typing import Dict
from gcis.core.enums import SignalState

ALLOWED = {
    SignalState.DISCOVERED: [SignalState.QUALIFIED, SignalState.REJECTED, SignalState.BLOCKED, SignalState.EXPIRED, SignalState.INVALIDATED],
    SignalState.QUALIFIED: [SignalState.ARMED, SignalState.BLOCKED, SignalState.EXPIRED, SignalState.INVALIDATED, SignalState.CANCELLED],
    SignalState.ARMED: [SignalState.TRIGGERED, SignalState.BLOCKED, SignalState.EXPIRED, SignalState.INVALIDATED, SignalState.CANCELLED],
    SignalState.TRIGGERED: [SignalState.EXECUTED, SignalState.BLOCKED, SignalState.EXPIRED, SignalState.INVALIDATED, SignalState.CANCELLED],
    SignalState.BLOCKED: [SignalState.QUALIFIED, SignalState.ARMED, SignalState.EXPIRED, SignalState.INVALIDATED, SignalState.CANCELLED],
    # terminals: no outgoing
}

def can_transition(frm: str, to: str) -> bool:
    try:
        frm_e = SignalState(frm)
        to_e = SignalState(to)
    except:
        return False
    if frm_e in (SignalState.EXECUTED, SignalState.REJECTED, SignalState.EXPIRED, SignalState.CANCELLED, SignalState.INVALIDATED):
        return False
    allowed = ALLOWED.get(frm_e, [])
    return to_e in allowed

def ttl_for_timeframe(tf: str, config: dict) -> timedelta:
    ttl_bars = config.get("signal",{}).get("ttl_bars", {"5m":12,"15m":8,"1h":6})
    bars = ttl_bars.get(tf, 8)
    # map timeframe to minutes
    tf_min = {"1m":1,"5m":5,"15m":15,"1h":60,"4h":240,"1d":1440}
    mins = tf_min.get(tf, 15) * bars
    return timedelta(minutes=mins)

def compute_expiry(created_at: datetime, timeframe: str, config: dict) -> datetime:
    return created_at + ttl_for_timeframe(timeframe, config)
