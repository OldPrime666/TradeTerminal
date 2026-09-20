"""
ICT-09 Premium / Discount + OTE (Optimal Trade Entry)
Config:
  ote_low 0.62
  ote_high 0.79
  require_discount_for_long true
  require_premium_for_short true
  htf_ltf_conflict_policy NO_TRADE (dealt in htf module)

Definition:
  Dealing range from recent swing high/low that defines current structure.
  Equivalent simplified: recent_high = max high of last N (or last swing high pair),
                        recent_low  = min low of last N
  Equilibirium 0.50 = (high+low)/2
  Premium = price > eq (upper half)
  Discount = price < eq (lower half)
  OTE = price within [high - 0.79*range, high - 0.62*range] for bearish retrace?
        For bullish impulse (from low to high), OTE long is retrace 62-79% of impulse.
        Simplified generic: OTE zone = low + 0.62*range  to  low + 0.79*range ? Actually that is discount premium?
        Let's define:
          If direction LONG (buy discount), OTE zone = recent_low + 0.62*range ... recent_low +0.79*range? No that's still lower half but Fibonacci retrace of prior up move.
          Simpler: OTE zone expressed as premium/discount specific: For longing in discount, OTE is 62-79% of the dealing range from high down.
          So OTE_low = low + 0.21*range? Hmm confusion.

        Typical ICT OTE: In a bullish market structure, you wait for price to retrace 62-79% of the last bullish displacement (from low to high).
        So OTE region = high - 0.79*impulse_range  ... high -0.62*impulse_range  (between 62% and 79% retrace)
        Equivalent to low +0.21*range ... low+0.38*range  (since range=high-low, retrace 62% from high = low+0.38*range, 79% from high = low+0.21*range)

        For short, OTE = low +0.62*range ... low+0.79*range (i.e., upper half retrace).

  We'll implement both interpretations via functions.

  require_discount_for_long: if true, longs only allowed when price <= eq (discount) and ideally within OTE discount.
  require_premium_for_short: shorts only when price >= eq.

ICT-11 relative: all in relative ATR not absolute.

Causal: uses only closed bars.
"""
from decimal import Decimal
from typing import Tuple, Optional
import pandas as pd

def compute_dealing_range(df: pd.DataFrame, lookback: int = 20) -> Tuple[float, float]:
    if df is None or df.empty:
        return (0.0, 0.0)
    slice_ = df.tail(lookback) if len(df) >= lookback else df
    high = float(slice_["high"].max())
    low = float(slice_["low"].min())
    return (low, high)

def compute_ote_zones(low: float, high: float, cfg: dict = None) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """
    Returns (ote_long_zone, ote_short_zone)
    ote_long_zone for buying discount: low +0.21*range to low+0.38*range (62-79% retrace from high)
    ote_short_zone for selling premium: high -0.38*range to high -0.21*range? Actually opposite: low+0.62*range to low+0.79*range
    Simplified: long OTE = discount retrace, short OTE = premium retrace.
    """
    if cfg is None:
        cfg = {}
    ote_low = cfg.get("ote_low", 0.62)
    ote_high = cfg.get("ote_high", 0.79)
    rng = high - low
    if rng <= 0:
        return ((low, high), (low, high))
    # For long, retrace from high: level = high - fib*range
    long_low = high - ote_high * rng
    long_high = high - ote_low * rng
    # For short, retrace from low: level = low + fib*range
    short_low = low + ote_low * rng
    short_high = low + ote_high * rng
    # Ensure ordered
    long_zone = (min(long_low, long_high), max(long_low, long_high))
    short_zone = (min(short_low, short_high), max(short_low, short_high))
    return (long_zone, short_zone)

def is_premium(price: float, low: float, high: float) -> bool:
    eq = (low + high) / 2
    return price > eq

def is_discount(price: float, low: float, high: float) -> bool:
    eq = (low + high) / 2
    return price <= eq

def is_in_ote(price: float, zone: Tuple[float, float]) -> bool:
    return zone[0] <= price <= zone[1]

def check_premium_discount(
    price: float,
    low: float,
    high: float,
    direction: str,
    cfg: dict = None,
) -> Tuple[bool, str]:
    """
    Returns (pass, reason)
    For LONG require discount (+ optionally OTE), for SHORT require premium.
    If cfg require_discount_for_long false, always pass.
    """
    if cfg is None:
        cfg = {}
    require_discount = cfg.get("require_discount_for_long", True)
    require_premium = cfg.get("require_premium_for_short", True)
    ote_low = cfg.get("ote_low", 0.62)
    ote_high = cfg.get("ote_high", 0.79)
    rng = high - low
    eq = (low + high) / 2
    if direction == "LONG":
        if require_discount and price > eq:
            return (False, "PREMIUM_NOT_DISCOUNT")
        # optionally check OTE: if price in discount but outside OTE maybe still pass? Spec says OTE 0.62-0.79 is optimal.
        # We will not block outside OTE, just flag. For strict test, require within OTE long zone?
        # Let's not block purely on OTE unless caller asks.
        return (True, "DISCOUNT_OK")
    elif direction == "SHORT":
        if require_premium and price < eq:
            return (False, "DISCOUNT_NOT_PREMIUM")
        return (True, "PREMIUM_OK")
    return (True, "NO_DIRECTION")

def check_ote(price: float, low: float, high: float, direction: str, cfg: dict = None) -> bool:
    ote_long, ote_short = compute_ote_zones(low, high, cfg)
    zone = ote_long if direction == "LONG" else ote_short
    return is_in_ote(price, zone)
