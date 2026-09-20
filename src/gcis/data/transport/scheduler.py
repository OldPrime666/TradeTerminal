"""
ARC-20 prioritised scheduling + bundle budget 20s (scale design).
Groups: klines_1m base, all_market, focus_set (open_positions, armed_signals, operator_pins)
Priorities: landing (top), scanner (high), level2 (mid), derivatives (low), in-risk-set boost.
Bundle budget 20s -> ANALYSIS_LAG (never silent skip); NOT_SUBSCRIBED for beyond budget.
Deterministic sorting, no external.
"""
from typing import List, Dict, Any, Set
import time

# Priority weights (higher first)
PRIORITY_ORDER = ["landing", "scanner", "level2", "derivatives", "in_risk_set", "other"]

def prioritise_symbols(
    symbols: List[str],
    landing_set: Set[str] | None = None,
    scanner_set: Set[str] | None = None,
    level2_set: Set[str] | None = None,
    derivatives_set: Set[str] | None = None,
    in_risk_set: Set[str] | None = None,
    operator_pins: Set[str] | None = None,
) -> List[str]:
    """
    Sort symbols by priority: landing > scanner > level2 > derivatives > in_risk_set > other
    Within each tier, alphabetical for determinism.
    Operator pins are promoted to landing tier.
    """
    landing_set = landing_set or set()
    scanner_set = scanner_set or set()
    level2_set = level2_set or set()
    derivatives_set = derivatives_set or set()
    in_risk_set = in_risk_set or set()
    operator_pins = operator_pins or set()
    # merge landing + pins
    landing = set(landing_set) | set(operator_pins)
    # assign tier
    tier_map: Dict[str,int] = {}
    for s in symbols:
        if s in landing:
            tier_map[s]=0
        elif s in scanner_set:
            tier_map[s]=1
        elif s in level2_set:
            tier_map[s]=2
        elif s in derivatives_set:
            tier_map[s]=3
        elif s in in_risk_set:
            tier_map[s]=4
        else:
            tier_map[s]=5
    # sort by tier then alphabetical
    return sorted(symbols, key=lambda s: (tier_map[s], s))

def schedule_bundles(
    prioritized_symbols: List[str],
    bundle_latency_budget_s: float = 20.0,
    per_symbol_ms: float = 50.0,
    per_candle_overhead_ms: float = 2.0,
    candles_per_symbol: int = 6,
) -> Dict[str, Any]:
    """
    Simulate bundle processing time: per symbol cost = per_symbol_ms + candles_per_symbol * overhead
    Returns processed list and lag status.
    If total would exceed budget, remaining symbols marked NOT_SUBSCRIBED (never silently skipped without status).
    """
    total_ms = 0.0
    processed: List[str] = []
    not_subscribed: List[str] = []
    per_symbol_cost = per_symbol_ms + candles_per_symbol * per_candle_overhead_ms
    budget_ms = bundle_latency_budget_s * 1000.0
    for sym in prioritized_symbols:
        if total_ms + per_symbol_cost <= budget_ms:
            processed.append(sym)
            total_ms += per_symbol_cost
        else:
            not_subscribed.append(sym)
            # Still need to record status but not process
    # status
    if not_subscribed:
        status = "ANALYSIS_LAG"
        detail = f"budget {bundle_latency_budget_s}s exceeded; processed {len(processed)}/{len(prioritized_symbols)}, {len(not_subscribed)} NOT_SUBSCRIBED"
    else:
        status = "OK"
        detail = f"all {len(processed)} processed within {bundle_latency_budget_s}s budget ({total_ms/1000:.2f}s)"
    return {
        "processed": processed,
        "not_subscribed": not_subscribed,
        "total_ms": round(total_ms,2),
        "budget_ms": budget_ms,
        "status": status,
        "detail": detail,
        "per_symbol_ms": per_symbol_cost,
        "note": "ARC-20 sharded WS prioritised scheduling + bundle budget never silent skip"
    }

def plan_with_priority(
    symbols: List[str],
    focus_symbols: List[str] | None = None,
    landing: Set[str] | None = None,
    scanner: Set[str] | None = None,
    level2: Set[str] | None = None,
    derivatives: Set[str] | None = None,
    in_risk: Set[str] | None = None,
    operator_pins: Set[str] | None = None,
    max_per_conn: int = 180,
    budget_s: float = 20.0,
) -> Dict[str, Any]:
    """
    Combines prioritisation + sharding + schedule.
    Returns plan shards and schedule status.
    """
    from gcis.data.transport.sharding import plan_shards
    prioritized = prioritise_symbols(symbols, landing, scanner, level2, derivatives, in_risk, operator_pins)
    plan = plan_shards(prioritized, focus_symbols or list(in_risk or []), max_per_conn)
    # schedule only prioritized symbols (representing engine work, not necessarily WS shards)
    sched = schedule_bundles(prioritized, bundle_latency_budget_s=budget_s)
    return {
        "prioritized": prioritized,
        "plan": plan,
        "schedule": sched,
        "shard_summary": {k: {"shards": len(v), "streams": sum(len(s) for s in v)} for k,v in plan.items()},
        "prioritised_note": "landing > scanner > level2 > derivatives > in_risk > other"
    }
