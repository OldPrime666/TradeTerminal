"""
EXE-05 Position management — conservative paper
Tracks quantity, entry_price, stop, tp, leverage, margin, unrealized/realized PnL
"""
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Tuple

def open_position(symbol: str, direction: str, quantity: Decimal, entry_price: Decimal, stop: Decimal, tp1: Decimal = None, tp2: Decimal = None, leverage: int = 3, margin: Decimal = None) -> Dict:
    qty = Decimal(str(quantity))
    entry = Decimal(str(entry_price))
    return {
        "symbol": symbol,
        "direction": direction,
        "quantity": qty,
        "entry_price": entry,
        "stop_loss": Decimal(str(stop)) if stop is not None else None,
        "take_profit_1": Decimal(str(tp1)) if tp1 is not None else None,
        "take_profit_2": Decimal(str(tp2)) if tp2 is not None else None,
        "leverage": leverage,
        "margin": margin or (qty * entry / Decimal(leverage) if leverage else qty*entry),
        "unrealized_pnl": Decimal("0"),
        "realized_pnl": Decimal("0"),
        "state": "OPEN",
        "opened_at": datetime.now(timezone.utc),
    }

def update_position_mark(position: Dict, mark_price: Decimal) -> Dict:
    pos = dict(position)
    entry = Decimal(str(pos["entry_price"]))
    qty = Decimal(str(pos["quantity"]))
    mark = Decimal(str(mark_price))
    if pos["direction"] == "LONG":
        pnl = qty * (mark - entry)
    else:
        pnl = qty * (entry - mark)
    pos["unrealized_pnl"] = pnl
    pos["mark_price"] = mark
    pos["current_price"] = mark
    return pos

def close_position(position: Dict, close_price: Decimal, quantity: Decimal) -> Tuple[Decimal, Dict]:
    """
    Closes quantity at close_price, returns (realized_pnl for this close, remaining_position dict)
    If quantity == position quantity => close fully.
    """
    pos = dict(position)
    entry = Decimal(str(pos["entry_price"]))
    qty_close = Decimal(str(quantity))
    qty_total = Decimal(str(pos["quantity"]))
    close = Decimal(str(close_price))
    if pos["direction"] == "LONG":
        pnl = qty_close * (close - entry)
    else:
        pnl = qty_close * (entry - close)
    # update realized
    pos["realized_pnl"] = Decimal(str(pos.get("realized_pnl", Decimal("0")))) + pnl
    remaining_qty = qty_total - qty_close
    if remaining_qty <= Decimal("0"):
        pos["quantity"] = Decimal("0")
        pos["state"] = "CLOSED"
        pos["closed_at"] = datetime.now(timezone.utc)
        pos["unrealized_pnl"] = Decimal("0")
    else:
        pos["quantity"] = remaining_qty
        # unrealized recalc at close_price as mark
        if pos["direction"] == "LONG":
            pos["unrealized_pnl"] = remaining_qty * (close - entry)
        else:
            pos["unrealized_pnl"] = remaining_qty * (entry - close)
    return pnl, pos
