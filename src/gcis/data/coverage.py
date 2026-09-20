"""
DAT-19 coverage_reports — analysed / listed ratio, with gap and eligibility.
Provides coverage report per venue/timeframe for dashboard banner.
"""
from typing import Dict, Any, List
from datetime import datetime, timezone

def coverage_report(all_contracts: List[Dict[str,Any]], eligible_contracts: List[Dict[str,Any]], candles_counts: Dict[str,int] | None =None, min_history_bars: int =300) -> Dict[str,Any]:
    """
    all_contracts: from registry (TRADING)
    eligible: after eligibility filter
    candles_counts: dict symbol -> count of 1m candles in archive
    Returns coverage metrics.
    """
    total = len(all_contracts)
    eligible_count = len(eligible_contracts)
    # analysed = those with >= min_history_bars
    if candles_counts is None:
        candles_counts = {}
    analysed = 0
    analysed_symbols=[]
    for c in eligible_contracts:
        sym = c.get("symbol")
        cnt = candles_counts.get(sym, 0)
        if cnt >= min_history_bars:
            analysed +=1
            analysed_symbols.append(sym)
    # also include non-eligible but analysed? For banner we report analysed/listed where listed = total, analysed = eligible with history
    ratio = analysed / total if total else 0
    eligible_ratio = eligible_count / total if total else 0
    return {
        "total_listed": total,
        "eligible": eligible_count,
        "analysed": analysed,
        "analysed_symbols_sample": analysed_symbols[:5],
        "coverage_ratio": round(ratio,4),
        "eligible_ratio": round(eligible_ratio,4),
        "min_history_bars": min_history_bars,
        "status": "HEALTHY" if ratio >=0.98 else "DEGRADED" if ratio >=0.90 else "LOW_COVERAGE" if total else "NO_DATA",
        "note": "DAT-19 coverage analysed/listed, min_history 300 bars"
    }

def banner_coverage_text(report: Dict[str,Any]) -> str:
    return f"{report['analysed']}/{report['total_listed']} analysed ({report['coverage_ratio']*100:.1f}%)"
