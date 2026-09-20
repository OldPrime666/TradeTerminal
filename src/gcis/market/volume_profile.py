"""
VOL-01 volume profile from candles (aggTrades fallback will be P3 DOM).
Computes histogram price by volume, POC, value area 70%.
Deterministic, no external.
"""
from typing import List, Dict, Any
import math
from decimal import Decimal

def compute_volume_profile(candles: List[Dict[str, Any]], bins: int = 24, value_area_pct: float = 0.70) -> Dict[str, Any]:
    """
    candles: list of dicts with high, low, close, volume (float or Decimal)
    bins: number of price bins (default 24 ~ 1h profile)
    Returns poc price, value_area low/high, profile histogram, total volume.
    """
    if not candles or bins <=0:
        return {"status":"NO_DATA","poc":None,"value_area":None,"profile":[],"total_volume": 0}
    # Find price range
    try:
        lows = [float(c["low"]) for c in candles]
        highs = [float(c["high"]) for c in candles]
        vols = [float(c["volume"]) for c in candles]
    except Exception:
        return {"status":"INVALID","poc":None,"value_area":None,"profile":[],"total_volume":0}
    low = min(lows)
    high = max(highs)
    if high <= low:
        return {"status":"NO_RANGE","poc":None,"value_area":None,"profile":[],"total_volume": sum(vols)}
    bin_width = (high - low) / bins
    if bin_width <=0:
        bin_width = 0.01
    # histogram: bucket midpoint vs volume
    buckets = [0.0]*bins
    bucket_low = [low + i*bin_width for i in range(bins)]
    bucket_high = [low + (i+1)*bin_width for i in range(bins)]
    bucket_mid = [(a+b)/2 for a,b in zip(bucket_low, bucket_high)]
    for c in candles:
        # Use typical price (close) for binning, volume attributed to that bin
        tp = float(c.get("close", c.get("low")))
        vol = float(c.get("volume",0))
        # find bin index
        idx = int((tp - low) / bin_width)
        idx = max(0, min(bins-1, idx))
        buckets[idx] += vol
    total = sum(buckets)
    if total ==0:
        return {"status":"NO_VOLUME","poc":None,"value_area":None,"profile":[],"total_volume":0}
    # POC: bucket with max volume
    poc_idx = max(range(bins), key=lambda i: buckets[i])
    poc = bucket_mid[poc_idx]
    # Value Area: Expand from POC outward accumulating volume until value_area_pct reached
    # Sort buckets by volume descending, take until sum >= 70%
    # But traditional Value Area expands contiguous from POC; we implement contiguous expansion
    left = poc_idx
    right = poc_idx
    accumulated = buckets[poc_idx]
    # expand one side at a time choosing higher volume side
    while accumulated < total * value_area_pct and (left >0 or right < bins-1):
        left_vol = buckets[left-1] if left>0 else -1
        right_vol = buckets[right+1] if right < bins-1 else -1
        if left_vol >= right_vol and left>0:
            left -=1
            accumulated += buckets[left]
        elif right < bins-1:
            right +=1
            accumulated += buckets[right]
        else:
            break
    va_low = bucket_low[left]
    va_high = bucket_high[right]
    profile = [{"low": round(bucket_low[i],4), "high": round(bucket_high[i],4), "mid": round(bucket_mid[i],4), "volume": round(buckets[i],2)} for i in range(bins)]
    return {
        "status":"OK",
        "poc": round(float(poc),4),
        "poc_volume": round(float(buckets[poc_idx]),2),
        "value_area": {"low": round(float(va_low),4), "high": round(float(va_high),4), "pct": value_area_pct},
        "profile": profile,
        "total_volume": round(float(total),2),
        "bins": bins,
        "note": "VOL-01 volume profile from candles; aggTrades DOM will enhance P3."
    }
