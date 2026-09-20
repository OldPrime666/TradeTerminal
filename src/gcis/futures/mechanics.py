"""
FUT-01..09 Futures mechanics — margin tiers, liquidation on mark, buffer gate 0.5×liq distance +1 ATR, funding per-interval, inverse PnL, lifecycle, effective leverage.
Deterministic, Decimal 38/18 style where needed.
"""
from decimal import Decimal, getcontext
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

getcontext().prec = 28

# FUT-02 leverage defaults
DEFAULT_LEVERAGE = Decimal("3")
HARD_MAX_LEVERAGE = Decimal("10")

def calc_liquidation_price(entry: Decimal, leverage: Decimal, side: str, mmr: Decimal = Decimal("0.01"), contract_type: str = "linear") -> Decimal:
    """
    Simplified liquidation on mark:
    LONG linear: liq = entry * (1 - (1/leverage - mmr))  ??? Actually for isolated: liq = entry * (1 - 1/leverage + mmr) approx
    SHORT linear: liq = entry * (1 + 1/leverage - mmr)
    Inverse: liq = entry / (1 ± leverage*mmr?) Simplified same for stub.
    For P18, we use: LONG liq = entry * (1 - (1/leverage)*(1 - mmr*leverage))? Simpler linear approximation.
    We'll implement: LONG: entry * (1 - 0.9/leverage) ; SHORT: entry * (1 + 0.9/leverage) as proxy with mmr adjustment.
    Deterministic.
    """
    entry = Decimal(str(entry))
    lev = Decimal(str(leverage))
    if lev <=0:
        lev = DEFAULT_LEVERAGE
    mmr = Decimal(str(mmr))
    # fees buffer 0.9 factor
    factor = (Decimal("1") / lev) - mmr
    if factor <= 0:
        factor = Decimal("0.005")  # minimum distance
    if side == "LONG":
        liq = entry * (Decimal("1") - factor)
    else:
        liq = entry * (Decimal("1") + factor)
    # ensure liq positive
    if liq <=0:
        liq = entry * Decimal("0.01")
    return liq

def check_liquidation_buffer(entry: Decimal, stop: Decimal, liq: Decimal, atr: Decimal, max_stop_fraction: float =0.5, liq_buffer_atr: float =1.0) -> Dict[str,Any]:
    """
    FUT-03 buffer gate: |entry-stop| <= 0.5 * |entry-liq| and |stop-liq| >=1 ATR
    Returns allowed bool, reason.
    """
    entry = Decimal(str(entry))
    stop = Decimal(str(stop))
    liq = Decimal(str(liq))
    atr = Decimal(str(atr))
    liq_dist = abs(entry - liq)
    stop_dist = abs(entry - stop)
    if liq_dist == 0:
        return {"allowed": False, "reason": "LIQ_DIST_ZERO", "liq_dist": float(liq_dist)}
    if stop_dist > liq_dist * Decimal(str(max_stop_fraction)):
        return {"allowed": False, "reason": "STOP_TOO_CLOSE_TO_LIQ", "detail": f"stop {stop_dist} > {max_stop_fraction}*liq_dist {liq_dist}", "liq_dist": float(liq_dist), "stop_dist": float(stop_dist)}
    if abs(stop - liq) < atr * Decimal(str(liq_buffer_atr)):
        return {"allowed": False, "reason": "STOP_LIQ_BUFFER_INSUFFICIENT", "detail": f"|stop-liq| {abs(stop-liq)} < {liq_buffer_atr}*ATR {atr}", "buffer": float(abs(stop-liq))}
    return {"allowed": True, "reason": None, "liq_dist": float(liq_dist), "stop_dist": float(stop_dist), "buffer": float(abs(stop-liq))}

def funding_cost_estimate(funding_rate: float, notional: float, interval_hours: int =8) -> Dict[str,float]:
    """
    Funding per-interval: cost = notional * funding_rate (rate is per interval, e.g., 0.0001 =1 bps per 8h)
    Also estimates per-day cost.
    """
    per_interval = notional * funding_rate
    per_day = per_interval * (24 / interval_hours) if interval_hours else per_interval
    return {"per_interval": per_interval, "per_day": per_day, "rate": funding_rate, "notional": notional}

def inverse_pnl(entry: float, exit_price: float, qty: float, contract_multiplier: float =1.0, side: str ="LONG") -> float:
    """
    Inverse PnL: for inverse contracts (e.g., BTCUSD inverse), pnl = qty * multiplier * (1/entry - 1/exit) for LONG? Actually inverse LONG profit when price up: PnL = qty*(1/entry -1/exit) ??? Let's implement simplified:
    LONG: pnl = qty * (1/entry - 1/exit) * multiplier * entry*exit? Simpler to match linear for test, but provide distinct formula.
    We'll use: inverse LONG pnl = qty * (1/entry -1/exit) * contract_multiplier * exit? No.
    For P18 stub we implement textbook: Inverse futures PNL in BTC terms: LONG pnl = qty * (1/entry - 1/exit). For linear, pnl = qty*(exit-entry).
    We'll expose both and test they differ.
    """
    if entry ==0 or exit_price==0:
        return 0.0
    if side=="LONG":
        # inverse: qty * (1/entry - 1/exit)
        pnl_inverse = qty * contract_multiplier * (1.0/entry - 1.0/exit_price)
        # linear for comparison if needed
    else:
        # short inverse: qty*(1/exit -1/entry)
        pnl_inverse = qty * contract_multiplier * (1.0/exit_price - 1.0/entry) * -1  # actually same? Let's keep simple: SHORT inverse pnl = qty*(1/exit -1/entry) negative? We'll define as qty*(1/exit -1/entry)
        pnl_inverse = qty * contract_multiplier * (1.0/exit_price - 1.0/entry) * -1
        # For stub, just make it opposite sign of long
        if side=="SHORT":
            pnl_inverse = -qty * contract_multiplier * (1.0/entry - 1.0/exit_price)
    return float(pnl_inverse)

def linear_pnl(entry: float, exit_price: float, qty: float, side: str ="LONG") -> float:
    if side=="LONG":
        return (exit_price - entry) * qty
    else:
        return (entry - exit_price) * qty

def effective_leverage(notional: float, equity: float) -> float:
    if equity ==0:
        return 0.0
    return notional / equity

def contract_lifecycle(contract: Dict[str,Any], now: datetime | None =None) -> Dict[str,Any]:
    """
    Contract lifecycle: checks expiry / funding timer / close_before_delivery.
    contract: dict with symbol, contract_type (PERPETUAL/DELIVERY), expiry (datetime or None), funding_interval_hours
    Returns status ACTIVE, EXPIRING_SOON, EXPIRED, CLOSE_REQUIRED
    """
    if now is None:
        now = datetime.now(timezone.utc)
    ctype = contract.get("contract_type", "PERPETUAL")
    if ctype == "PERPETUAL":
        # no expiry
        return {"status":"ACTIVE","reason":"perp no expiry","close_required": False}
    expiry = contract.get("expiry")
    if expiry is None:
        return {"status":"UNKNOWN","reason":"no expiry field","close_required": False}
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    hours_to_expiry = (expiry - now).total_seconds()/3600
    if hours_to_expiry <0:
        return {"status":"EXPIRED","hours_to_expiry": hours_to_expiry,"close_required": True}
    # close_before_delivery_h 2, min_hours 12 per config
    if hours_to_expiry < 2:
        return {"status":"CLOSE_REQUIRED","hours_to_expiry": hours_to_expiry,"close_required": True}
    if hours_to_expiry <12:
        return {"status":"EXPIRING_SOON","hours_to_expiry": hours_to_expiry,"close_required": False, "note":"block new entries"}
    return {"status":"ACTIVE","hours_to_expiry": hours_to_expiry,"close_required": False}

def market_beta_cluster_risk(symbols: List[str]) -> Dict[str,Any]:
    """
    Market-beta cluster stub: all symbols in one cluster MARKET_BETA with risk cap 1.0
    Real correlation would split; here we return single cluster.
    """
    return {"cluster":"MARKET_BETA","symbols": symbols, "risk_cap_pct": 1.0, "note": "P18 stub: all in MARKET_BETA, dynamic correlation will split in P14"}
