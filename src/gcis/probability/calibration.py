"""
PRB Calibration — ECE, reliability, sigmoid/isotonic placeholder, drift.
Config: calibration default sigmoid, isotonic_min_oos 1000, drift window 50 ece_degrade 0.08
Deterministic.
"""
import math
from typing import List, Dict, Any, Tuple

def compute_ece(y_true: List[int], y_prob: List[float], n_bins: int = 10) -> float:
    """
    Expected Calibration Error: sum |acc - conf| * bin_weight
    y_true 0/1, y_prob 0..1
    Deterministic binning by uniform width 0.1.
    """
    if not y_true or not y_prob or len(y_true) != len(y_prob):
        return 0.0
    n = len(y_true)
    bins = [ [] for _ in range(n_bins) ]
    bin_true = [ [] for _ in range(n_bins) ]
    for t,p in zip(y_true, y_prob):
        idx = min(int(p * n_bins), n_bins-1)
        bins[idx].append(p)
        bin_true[idx].append(t)
    ece = 0.0
    for i in range(n_bins):
        if not bins[i]:
            continue
        acc = sum(bin_true[i]) / len(bin_true[i])
        conf = sum(bins[i]) / len(bins[i])
        weight = len(bins[i]) / n
        ece += abs(acc - conf) * weight
    return float(ece)

def reliability_bins(y_true: List[int], y_prob: List[float], n_bins: int = 10) -> List[Dict[str,float]]:
    """Return per-bin acc/conf/count for reliability diagram."""
    if not y_true or len(y_true)!= len(y_prob):
        return []
    bins = [{"count":0,"acc":0,"conf":0} for _ in range(n_bins)]
    # accumulate
    cnt = [0]*n_bins
    sum_p = [0.0]*n_bins
    sum_t = [0]*n_bins
    for t,p in zip(y_true, y_prob):
        idx = min(int(p * n_bins), n_bins-1)
        cnt[idx]+=1
        sum_p[idx]+=p
        sum_t[idx]+=t
    out=[]
    for i in range(n_bins):
        if cnt[i]==0:
            out.append({"bin": i, "low": i/n_bins, "high": (i+1)/n_bins, "count":0,"acc":None,"conf":None})
        else:
            out.append({"bin": i, "low": i/n_bins, "high": (i+1)/n_bins, "count": cnt[i], "acc": sum_t[i]/cnt[i], "conf": sum_p[i]/cnt[i]})
    return out

def sigmoid_calibration_placeholder(probs: List[float]) -> List[float]:
    """
    Sigmoid (Platt) would fit logistic; for P13 Tier A we keep identity (no-op) as placeholder.
    Isotonic requires >=1000 OOS per config, so not used in Tier A. We return probs unchanged but note.
    """
    return probs

def detect_drift(recent_ece: float, baseline_ece: float, threshold: float = 0.08) -> Dict[str,Any]:
    """
    PRB drift detection: window_events 50, threshold 0.08 degrade.
    If recent ECE - baseline ECE > threshold => drift flag.
    """
    degrade = recent_ece - baseline_ece
    drift = degrade > threshold
    return {"drift": drift, "degrade": degrade, "threshold": threshold, "recent_ece": recent_ece, "baseline_ece": baseline_ece}

def calibration_report(y_true: List[int], y_prob: List[float], n_bins: int = 10) -> Dict[str,Any]:
    ece = compute_ece(y_true, y_prob, n_bins)
    bins = reliability_bins(y_true, y_prob, n_bins)
    # Brier score as additional
    brier = sum((p - t)**2 for p,t in zip(y_prob, y_true)) / len(y_true) if y_true else None
    return {"ece": round(ece,4), "brier": round(brier,4) if brier is not None else None, "bins": bins, "n": len(y_true), "note": "ECE uniform 10 bins; Brier secondary. Sigmoid placeholder for Tier A."}
