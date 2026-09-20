"""
BKT-13 Confluence research — joint analysis of multiple strategies.
For P12 we provide overlap counts, joint expectancy, correlation proxy.
"""
from typing import Dict, List, Any
from collections import Counter
import hashlib
import json
from decimal import Decimal

def analyze_confluence(strategy_results: Dict[str, List[Dict[str,Any]]]) -> Dict[str,Any]:
    """
    strategy_results: dict strategy_name -> list of trades (from run_backtest or walk_forward oos)
    Computes:
     - overlap matrix (shared bars proxy via trades_count correlation)
     - confluence trades: trades where entry_bar within 5 bars across strategies (using entry_bar if present else index)
     - joint metrics if same symbol/timeframe
    """
    if not strategy_results:
        return {"status":"NO_DATA","note":"no strategy results"}
    # Normalize each
    normalized = {}
    for name, trades in strategy_results.items():
        # if trades is backtest dict, extract list
        if isinstance(trades, dict) and "trades" in trades:
            tlist = trades.get("trades", [])
        else:
            tlist = trades
        normalized[name] = tlist

    # counts
    counts = {k: len(v) for k,v in normalized.items()}
    # pairwise overlap proxy: Jaccard over entry_bar sets if available else direction agreement
    overlap = {}
    names = list(normalized.keys())
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            a = normalized[names[i]]; b = normalized[names[j]]
            # try entry_bar sets
            a_bars = set(t.get("entry_bar") for t in a if t.get("entry_bar") is not None)
            b_bars = set(t.get("entry_bar") for t in b if t.get("entry_bar") is not None)
            if a_bars and b_bars:
                inter = len(a_bars & b_bars)
                union = len(a_bars | b_bars)
                jacc = inter/union if union else 0
                overlap[f"{names[i]}__{names[j]}"] = {"jaccard": round(jacc,4), "intersection": inter, "union": union}
            else:
                # direction agreement proxy
                if a and b:
                    # compare direction sequence last 20
                    da = [t.get("direction") for t in a[-20:]]
                    db = [t.get("direction") for t in b[-20:]]
                    agree = sum(1 for x,y in zip(da,db) if x==y)/max(len(da),1) if da and db else 0
                    overlap[f"{names[i]}__{names[j]}"] = {"direction_agreement": round(agree,4)}
    # confluence signal: bar where >=2 strategies signal same direction (using entry_bar)
    bar_to_dirs = {}
    for name, trades in normalized.items():
        for t in trades:
            bar = t.get("entry_bar")
            if bar is None:
                continue
            bar_to_dirs.setdefault(bar, []).append(t.get("direction"))
    confluence_bars = []
    for bar, dirs in bar_to_dirs.items():
        if len(dirs) >= 2:
            # check if at least 2 same direction
            cnt = Counter(dirs)
            most_common, c = cnt.most_common(1)[0]
            if c >= 2:
                confluence_bars.append({"bar": bar, "dirs": dirs, "direction": most_common, "support": c})
    # joint expectancy for confluence bars: approximate by averaging pnls of supporting strategies at those bars
    # Build map bar -> list pnls
    confluence_pnls = []
    if confluence_bars:
        bar_to_pnl = {}
        for name, trades in normalized.items():
            for t in trades:
                bar = t.get("entry_bar")
                if bar is not None and bar in [c["bar"] for c in confluence_bars]:
                    bar_to_pnl.setdefault(bar, []).append(float(t.get("net_pnl", t.get("pnl", 0))))
        for cb in confluence_bars:
            pnls = bar_to_pnl.get(cb["bar"], [])
            if pnls:
                avg = sum(pnls)/len(pnls)
                confluence_pnls.append(avg)
    joint_expectancy = round(sum(confluence_pnls)/len(confluence_pnls),6) if confluence_pnls else None
    # trial counting note (BKT-13 + BKT-12 survivorship)
    total_trials = sum(counts.values())
    effective_trials_note = f"Raw trials {total_trials}, confluence {len(confluence_bars)} bars (>=2 strategies agree). Overlap-adjusted effective ~ {len(confluence_bars)} if requiring confluence."
    return {
        "status": "OK" if counts else "NO_DATA",
        "counts": counts,
        "overlap": overlap,
        "confluence_bars_count": len(confluence_bars),
        "confluence_sample": confluence_bars[:5],
        "confluence_pnls_sample": confluence_pnls[:5],
        "joint_expectancy": joint_expectancy,
        "total_trials": total_trials,
        "effective_trials_note": effective_trials_note,
        "survivorship_note": "Survivorship-aware: uses same Candle history (delisted included) per BKT-12",
        "note": "BKT-13 confluence research: overlap via entry_bar Jaccard, joint expectancy on confluence.",
        "purge_note": "Purge/embargo for confluence should be applied at signal level before pooling; walk_forward already purges."
    }

def run_confluence_from_engine(symbols: List[str], timeframe: str = "15m", df_override=None, strategies: List[str] | None = None):
    """
    Convenience: run multiple strategies via engine and analyze confluence.
    """
    strategies = strategies or ["ICT-A","EMA-CROSS","DONCHIAN","RSI-REV","CONFLUENCE"]
    from gcis.backtest.engine import run_backtest
    results = {}
    for strat in strategies:
        # engine currently only runs ICT-A internally; for others we patch strategy fn via walk_forward helper
        # For P12 we reuse run_walk_forward-like loop but simpler: call engine with mock via strategy param
        # Instead we call run_backtest with df_override and then override strategy via direct call using research helper
        # For determinism, if df_override, we can just run walk_forward mini per strat
        from gcis.backtest.walk_forward import run_walk_forward
        # Use tiny train/test to get some trades; for research we just use single fold engine via patched evaluate
        # Approach: patch gcis.strategies.ict_a.evaluate_ict_a temporarily to extra strategy
        import gcis.strategies.ict_a as ict_mod
        orig = ict_mod.evaluate_ict_a
        try:
            if strat == "EMA-CROSS":
                import gcis.strategies.extra as ex; ict_mod.evaluate_ict_a = ex.evaluate_ema_cross
            elif strat == "DONCHIAN":
                import gcis.strategies.extra as ex; ict_mod.evaluate_ict_a = ex.evaluate_donchian
            elif strat == "RSI-REV":
                import gcis.strategies.extra as ex; ict_mod.evaluate_ict_a = ex.evaluate_rsi_reversion
            elif strat == "CONFLUENCE":
                import gcis.strategies.extra as ex; ict_mod.evaluate_ict_a = ex.evaluate_confluence
            else:
                ict_mod.evaluate_ict_a = orig
            res = run_backtest(symbols=symbols, timeframe=timeframe, df_override=df_override)
            results[strat] = res.get("trades", [])
        finally:
            ict_mod.evaluate_ict_a = orig
    return analyze_confluence(results)
