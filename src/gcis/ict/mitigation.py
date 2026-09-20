"""
ICT-07 Mitigation — causal
Types: FVG and OB mitigation.

FVG mitigation (bullish):
  zone [lower, upper] where lower = high[i-2], upper = low[i], midpoint = (lower+upper)/2
  Config mitigation 50pct_or_full:
    MITIGATED if close <= midpoint? Actually for bullish FVG, price returning down into gap.
    - TOUCHED if wick low <= upper (enters gap)
    - MITIGATED if low <= midpoint (50%) OR close <= lower (full fill) OR close within zone for 50%? We'll use:
        MITIGATED if low <= midpoint (50% penetration)  (50pct)
        OR close <= lower (full)
        OR wick penetrates beyond lower and closes outside (invalidation?)? Simplified.
  For bearish opposite: high >= midpoint or close >= upper.

OB mitigation:
  zone [zone_low, zone_high]
  Bulish OB: mitigation when low <= zone_high? Typically order block is touched.
  We'll define:
    TOUCHED if low <= zone_high and low >= zone_low? Actually if wick enters zone.
    MITIGATED if close < zone_low (breaks through) ??? But for OB, mitigation is hold: price taps OB then displacement away.
    Simplified: TOUCHED if low <= zone_high (wick enters)
              MITIGATED if low <= zone_high and close > zone_low? Actually hold. Let's define:
                MITIGATED when price wick touches zone and then displaces away (close back above zone for bullish).
                For generic mitigation, we say MITIGATED if low <= zone_high and later close > zone_high with displacement.
                Simpler for now: MITIGATED if low <= (zone_low+zone_high)/2 (50% of OB)
                TOUCHED if low <= zone_high but not 50%.
  max_age_bars: if not mitigated within max_age, INVALIDATED.

Causal: sweep forward from created_index onward; status updated at bar close.

ICT-10 max_age: FVG 200, OB 300 as per config.

No repaint: once MITIGATED it stays, not reverted.

ICT-11 relative already via zone.
"""
from dataclasses import dataclass
from typing import List
import pandas as pd

def update_fvg_status(fvgs: List, df: pd.DataFrame, cfg: dict = None) -> List:
    if cfg is None:
        cfg = {}
    max_age = cfg.get("max_age_bars", 200)
    mitigation_mode = cfg.get("mitigation", "50pct_or_full")
    for fvg in fvgs:
        if fvg.status == "MITIGATED" or fvg.status == "INVALIDATED":
            continue
        # find df index of created (fvg.created_index)
        start = fvg.created_index + 1
        if start >= len(df):
            continue
        touched = False
        mitigated = False
        invalid = False
        for i in range(start, len(df)):
            # age check
            age = i - fvg.created_index
            if age > max_age and not touched:
                invalid = True
                break
            row = df.iloc[i]
            low = float(row["low"])
            high = float(row["high"])
            close = float(row["close"])
            lower_f = float(fvg.lower)
            upper_f = float(fvg.upper)
            mid_f = float(fvg.midpoint)
            if fvg.direction == "BULL":
                # wick touches upper = enters
                if low <= upper_f:
                    touched = True
                # mitigation 50pct or full
                if mitigation_mode == "50pct_or_full":
                    if low <= mid_f or close <= lower_f:
                        mitigated = True
                        break
                    # also close inside zone 50%? if close <= mid? already low <= mid captures
                else:
                    if low <= lower_f:
                        mitigated = True
                        break
                # for break beyond lower, also mitigated
                if high < lower_f:
                    mitigated = True
                    break
            else:  # BEAR
                if high >= lower_f:  # lower_f is lower for bear? For bear upper=low_im2, lower=high_i, check high >= lower
                    # Actually for bear: upper = low_im2, lower = high_i, zone [lower, upper] (lower < upper)
                    # Wick enters when high >= lower
                    if high >= lower_f:
                        touched = True
                    if high >= mid_f or close >= upper_f:
                        mitigated = True
                        break
            # if we have touched but not yet mitigated continue
        if mitigated:
            fvg.status = "MITIGATED"
        elif touched:
            fvg.status = "TOUCHED"
        elif invalid:
            fvg.status = "INVALIDATED"
        # else stays FRESH
    return fvgs

def update_ob_status(obs: List, df: pd.DataFrame, cfg: dict = None, atr_series=None, displacement_indices=None) -> List:
    if cfg is None:
        cfg = {}
    max_age = cfg.get("max_age_bars", 300)
    # displacement requirement for mitigation? For OB, valid mitigation requires displacement away after touch
    # We'll simple: TOUCHED if wick enters zone, MITIGATED if wick enters midpoint or displacement after.
    for ob in obs:
        if ob.mitigation_state in ("MITIGATED", "INVALIDATED"):
            continue
        start = ob.break_index + 1
        if start >= len(df):
            continue
        touched = False
        mitigated = False
        valid_disp_after = False
        disp_set = set(displacement_indices) if displacement_indices is not None else None
        for i in range(start, len(df)):
            age = i - ob.origin_index
            if age > max_age and not touched:
                ob.mitigation_state = "INVALIDATED"
                break
            row = df.iloc[i]
            low = float(row["low"])
            high = float(row["high"])
            close = float(row["close"])
            zl = float(ob.zone_low)
            zh = float(ob.zone_high)
            mid = (zl + zh) / 2
            if ob.direction == "BULL":
                if low <= zh:
                    touched = True
                    # check if mitigated: touch midpoint or displacement away
                    if low <= mid:
                        # need displacement away within next 3 bars? Check later bars for displacement
                        if disp_set is not None:
                            # Look ahead 3 bars from this touch for displacement bullish away (close > high?)
                            for kk in range(1, 4):
                                if i + kk < len(df) and (i + kk) in disp_set:
                                    # displacement after touch => mitigated
                                    mitigated = True
                                    break
                            if mitigated:
                                break
                        else:
                            mitigated = True
                            break
                    # also if close back above zone with displacement
                    # simple: if low touched and close > zh → still touched not mitigated until 50%
            else:  # BEAR
                if high >= zl:
                    touched = True
                    if high >= mid:
                        if disp_set is not None:
                            for kk in range(1, 4):
                                if i + kk < len(df) and (i + kk) in disp_set:
                                    mitigated = True
                                    break
                            if mitigated:
                                break
                        else:
                            mitigated = True
                            break
        if ob.mitigation_state == "INVALIDATED":
            continue
        if mitigated:
            ob.mitigation_state = "MITIGATED"
        elif touched:
            ob.mitigation_state = "TOUCHED"
    return obs

def check_fvg_mitigation(fvg, df: pd.DataFrame, cfg: dict = None) -> str:
    """
    Single FVG check helper for tests: returns status after scanning df from created onward.
    """
    res = update_fvg_status([fvg], df, cfg)
    return res[0].status if res else fvg.status
