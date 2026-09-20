"""
RSK-02 Daily state 00:00 UTC incl unrealised
DailyRiskState keyed by risk_day YYYY-MM-DD UTC.
starting_equity reset at 00:00 UTC to current equity (including unrealised).
Helper functions for tests.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict

def should_reset_daily(last_time: datetime, current_time: datetime) -> bool:
    """
    Returns True if current_time is on next UTC day vs last_time.
    Uses date comparison in UTC.
    """
    if last_time is None or current_time is None:
        return False
    # normalize to UTC
    last_utc = last_time.astimezone(timezone.utc) if last_time.tzinfo else last_time.replace(tzinfo=timezone.utc)
    cur_utc = current_time.astimezone(timezone.utc) if current_time.tzinfo else current_time.replace(tzinfo=timezone.utc)
    return cur_utc.date() > last_utc.date()

def reset_daily_state(state: Dict, current_time: datetime, current_equity: Decimal) -> Dict:
    """
    Resets starting_equity to current_equity for new day.
    state dict with keys risk_day, starting_equity, current_equity, daily_loss
    """
    new_day = current_time.astimezone(timezone.utc).date().isoformat() if current_time.tzinfo else current_time.replace(tzinfo=timezone.utc).date().isoformat()
    return {
        "risk_day": new_day,
        "starting_equity": Decimal(str(current_equity)),
        "current_equity": Decimal(str(current_equity)),
        "daily_loss": Decimal("0"),
        "trades_today": 0,
        "risk_lock": "ACTIVE",
    }

def compute_daily_loss_pct(starting_equity: Decimal, current_equity: Decimal, unrealized_pnl: Decimal = Decimal("0")) -> Decimal:
    """
    Daily loss pct including unrealised: (starting - (current+unrealized))/starting *100
    """
    if starting_equity == 0:
        return Decimal("0")
    total = Decimal(str(current_equity)) + Decimal(str(unrealized_pnl))
    loss = Decimal(str(starting_equity)) - total
    return (loss / Decimal(str(starting_equity))) * Decimal("100")

def is_daily_loss_lock(starting_equity: Decimal, current_equity: Decimal, unrealized_pnl: Decimal, max_daily_loss_pct: Decimal) -> bool:
    loss_pct = compute_daily_loss_pct(starting_equity, current_equity, unrealized_pnl)
    return loss_pct >= Decimal(str(max_daily_loss_pct))
