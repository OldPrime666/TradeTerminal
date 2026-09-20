"""
RSK-04 dynamic correlation — market-beta clustering.
Config: correlation dynamic enabled true, lookback 30d, return_timeframe 1h, link_abs_rho 0.70, min_overlap 200, insufficient treat_as_correlated
Deterministic, no lookahead.
"""
import math
from typing import Dict, List, Any, Tuple
import numpy as np

def compute_returns(prices: List[float]) -> List[float]:
    out=[]
    for i in range(1,len(prices)):
        if prices[i-1]==0:
            out.append(0.0)
        else:
            out.append(prices[i]/prices[i-1] - 1)
    return out

def pairwise_correlations(returns_dict: Dict[str, List[float]]) -> Dict[Tuple[str,str], float]:
    """
    Compute Pearson correlation for each pair with overlap handling.
    Returns dict (a,b) -> rho (float) or 0 if insufficient.
    Deterministic via numpy.corrcoef (linear).
    """
    syms = list(returns_dict.keys())
    out={}
    for i in range(len(syms)):
        for j in range(i+1, len(syms)):
            a = np.array(returns_dict[syms[i]], dtype=float)
            b = np.array(returns_dict[syms[j]], dtype=float)
            # align length: use min len (overlap) naive; better to truncate to min
            n = min(len(a), len(b))
            if n < 2:
                out[(syms[i], syms[j])] = 0.0
                continue
            a = a[-n:]
            b = b[-n:]
            # if constant series, corr nan -> 0
            if np.std(a)==0 or np.std(b)==0:
                out[(syms[i], syms[j])] = 0.0
                continue
            rho = float(np.corrcoef(a,b)[0,1])
            if math.isnan(rho):
                rho = 0.0
            out[(syms[i], syms[j])] = rho
            out[(syms[j], syms[i])] = rho
    return out

def cluster_by_threshold(symbols: List[str], corr: Dict[Tuple[str,str], float], threshold: float = 0.70) -> Dict[str, str]:
    """
    Greedy clustering: start each symbol alone, merge if |rho| >= threshold.
    Returns dict symbol -> cluster_id (e.g., cluster-0, cluster-1)
    Deterministic order by symbols sorted.
    """
    parent = {s: s for s in symbols}
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x
    def union(a,b):
        ra, rb = find(a), find(b)
        if ra!=rb:
            parent[rb]=ra
    # sort symbols for deterministic iteration
    syms = sorted(symbols)
    for i in range(len(syms)):
        for j in range(i+1, len(syms)):
            rho = corr.get((syms[i], syms[j]), 0.0)
            if abs(rho) >= threshold:
                union(syms[i], syms[j])
    # assign cluster ids
    clusters: Dict[str, List[str]] = {}
    for s in syms:
        r = find(s)
        clusters.setdefault(r, []).append(s)
    # map to cluster-0 etc. sort by representative
    sorted_reps = sorted(clusters.keys())
    out={}
    for idx, rep in enumerate(sorted_reps):
        cid = f"cluster-{idx}"
        for m in clusters[rep]:
            out[m]=cid
    return out

def dynamic_clusters(returns_dict: Dict[str, List[float]], lookback_days: int =30, return_timeframe: str="1h", link_abs_rho: float=0.70, min_overlap_bars: int=200, insufficient_data: str="treat_as_correlated", config: dict | None =None) -> Dict[str, Any]:
    """
    High-level: returns clustering result with handling insufficient data.
    If insufficient_data == treat_as_correlated and any symbol has < min_overlap_bars, then all in one cluster MARKET_BETA.
    Otherwise normal clustering.
    """
    if config:
        dyn = config.get("correlation",{}).get("dynamic",{})
        lookback_days = dyn.get("lookback_days", lookback_days)
        return_timeframe = dyn.get("return_timeframe", return_timeframe)
        link_abs_rho = dyn.get("link_abs_rho", link_abs_rho)
        min_overlap_bars = dyn.get("min_overlap_bars", min_overlap_bars)
        insufficient_data = dyn.get("insufficient_data", insufficient_data)
    symbols = list(returns_dict.keys())
    # check insufficient
    for sym, rets in returns_dict.items():
        if len(rets) < min_overlap_bars:
            if insufficient_data == "treat_as_correlated":
                # all correlated single cluster
                return {
                    "status": "INSUFFICIENT_DATA_TREAT_AS_CORRELATED",
                    "clusters": {s: "cluster-0" for s in symbols},
                    "corr": {},
                    "link_abs_rho": link_abs_rho,
                    "min_overlap_bars": min_overlap_bars,
                    "note": f"insufficient overlap {len(rets)}<{min_overlap_bars} => single cluster MARKET_BETA per config"
                }
    corr = pairwise_correlations(returns_dict)
    clusters = cluster_by_threshold(symbols, corr, threshold=link_abs_rho)
    # also include MARKET_BETA default cluster name if single
    return {
        "status": "OK",
        "clusters": clusters,
        "corr": {f"{k[0]}__{k[1]}": round(v,4) for k,v in corr.items() if k[0]<k[1]},  # only unique
        "link_abs_rho": link_abs_rho,
        "min_overlap_bars": min_overlap_bars,
        "note": f"dynamic clusters threshold |rho|>={link_abs_rho}"
    }

def is_correlated(symbol_a: str, symbol_b: str, clusters: Dict[str,str]) -> bool:
    return clusters.get(symbol_a) == clusters.get(symbol_b)

def cluster_risk_pct(cluster_id: str, config: dict | None = None) -> float:
    """Per-cluster risk cap: market_beta_cluster_risk_pct or max_per_cluster 1.0 """
    if config:
        # market_beta special
        if cluster_id == "cluster-0":
            return float(config.get("correlation",{}).get("market_beta_cluster_risk_pct", 1.0))
        return float(config.get("risk",{}).get("max_per_cluster_risk_pct", 1.0))
    return 1.0
