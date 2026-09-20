from decimal import Decimal, ROUND_DOWN

def compute_quantity(equity: Decimal, risk_pct: Decimal, entry: Decimal, stop: Decimal, fee_per_unit: Decimal, slippage_per_unit: Decimal, buffer_per_unit: Decimal, step_size: Decimal, min_qty: Decimal, min_notional: Decimal) -> Decimal:
    """
    quantity = risk_amount / (|entry-stop| + fees + slippage + buffer); round DOWN to step size; enforce tick/min filters; if min cannot be met -> block.
    INV-09 enforced via caller.
    """
    risk_amount = equity * (risk_pct / Decimal(100))
    distance = abs(entry - stop)
    denom = distance + fee_per_unit + slippage_per_unit + buffer_per_unit
    if denom <= 0:
        return Decimal("0")
    raw_qty = risk_amount / denom
    # round down to step_size
    if step_size and step_size != Decimal("0"):
        # quantize down
        # step_size like 0.001 => need to floor
        # use // operation
        steps = (raw_qty // step_size) * step_size
        qty = steps
    else:
        qty = raw_qty
    # enforce min qty and min notional
    if qty < min_qty:
        return Decimal("0")
    notional = qty * entry
    if notional < min_notional:
        return Decimal("0")
    return qty.quantize(Decimal("1.00000000")).normalize() if qty else Decimal("0")
