"""
BKT-09 Monte Carlo — block bootstrap for significance.
Deterministic seed 42, block_size from config backtest.monte_carlo.block_size, runs from monte_carlo.runs
"""
import random
import math
from typing import List, Dict, Any
import hashlib
from decimal import Decimal

def _seeded(seed: int):
    return random.Random(seed)

def block_bootstrap_trades(trades: List[Dict[str,Any]], block_size: int = 10, runs: int = 5000, seed: int = 42) -> Dict[str, Any]:
    """
    Bootstrap distribution of expectancy via block resampling with replacement.
    trades: list of dicts with net_pnl or pnl.
    Returns distribution stats and p-value vs zero.
    Deterministic via seed.
    """
    if not trades:
        return {"status":"INSUFFICIENT_TRADES","runs":0,"observed_expectancy": None, "distribution_mean": None, "p_value_vs_zero": None, "ci_95": (None,None), "note":"no trades"}

    # Normalize pnls
    pnls = []
    for t in trades:
        v = t.get("net_pnl", t.get("pnl", 0))
        if isinstance(v, Decimal):
            pnls.append(float(v))
        elif isinstance(v, str):
            try: pnls.append(float(Decimal(v)))
            except: pnls.append(0.0)
        else:
            pnls.append(float(v))
    n = len(pnls)
    if n < 10:
        return {"status":"DEGRADED_SMALL_SAMPLE","runs":0,"observed_expectancy": sum(pnls)/n if n else None, "note":"need >=10 trades for MC"}

    # block partition: create blocks of size block_size (non-overlapping, last smaller)
    blocks = []
    for i in range(0, n, block_size):
        blocks.append(pnls[i:i+block_size])
    num_blocks = len(blocks)
    # number of blocks needed per resample to match n (approx)
    blocks_per_sample = math.ceil(n / block_size)
    observed_expectancy = sum(pnls)/n
    rnd = _seeded(seed)
    # runs: cap to 5000 for speed, but config may ask more
    runs = min(runs, 5000) if runs and runs>0 else 5000
    boot_means = []
    for _ in range(runs):
        # draw blocks with replacement
        sample = []
        for _b in range(blocks_per_sample):
            b = rnd.choice(blocks)
            sample.extend(b)
        # truncate to n
        sample = sample[:n]
        boot_means.append(sum(sample)/n)
    boot_means.sort()
    mean_boot = sum(boot_means)/len(boot_means)
    # 95 CI percentile
    lo_idx = int(0.025 * len(boot_means))
    hi_idx = int(0.975 * len(boot_means))
    ci_lo = boot_means[lo_idx]
    ci_hi = boot_means[hi_idx]
    # p-value vs zero: fraction of bootstrapped means <=0 if observed >0 else >=0
    if observed_expectancy > 0:
        # one-sided p = proportion boot_mean <=0
        p_val = sum(1 for m in boot_means if m <= 0) / len(boot_means)
    elif observed_expectancy < 0:
        p_val = sum(1 for m in boot_means if m >= 0) / len(boot_means)
    else:
        p_val = 1.0
    # also sharpe-like distribution?
    # jitter allowance note
    return {
        "status":"OK",
        "observed_expectancy": round(observed_expectancy, 6),
        "distribution_mean": round(mean_boot, 6),
        "ci_95": (round(ci_lo,6), round(ci_hi,6)),
        "p_value_vs_zero": round(p_val,4),
        "runs": runs,
        "block_size": block_size,
        "n_trades": n,
        "num_blocks": num_blocks,
        "note": "Block bootstrap preserves autocorrelation block_size. p_value one-sided vs zero. CI 95 percentile.",
        "distribution_sample": boot_means[:5],  # small sample for inspection
        "jitter": "deterministic seed 42"
    }

def monte_carlo_from_backtest(backtest_result: Dict[str,Any], block_size: int | None = None, runs: int | None = None, seed: int =42) -> Dict[str,Any]:
    """
    Helper to run MC directly from run_backtest output.
    """
    from gcis.core.config import get_config
    cfg = get_config()
    mc_cfg = cfg.get("backtest",{}).get("monte_carlo", {})
    block_size = block_size if block_size is not None else mc_cfg.get("block_size", 10)
    runs = runs if runs is not None else mc_cfg.get("runs", 5000)
    trades = backtest_result.get("trades", [])
    # backtest trades may be capped to 20; need full count? Use trades provided; warn if capped
    if backtest_result.get("trades_count", len(trades)) > len(trades):
        note = f"WARNING: backtest trades capped {len(trades)}/{backtest_result.get('trades_count')} — MC on sample only (capped). For full, use trades_count with bootstrap on extended output."
    else:
        note = "MC on full trades list"
    out = block_bootstrap_trades(trades, block_size=block_size, runs=runs, seed=seed)
    out["source_note"] = note
    return out
