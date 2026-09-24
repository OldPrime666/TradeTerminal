"""Phase11: risk guard paper-only, fail closed, leverage caps."""
HARD_CAP=10
DEFAULT_CAP=3
def check_leverage(leverage: float, requested: float) -> bool:
    return leverage <= HARD_CAP and requested <= DEFAULT_CAP
def check_notional(notional: float, max_notional: float = 10000) -> bool:
    return notional <= max_notional
def fail_closed(reason: str):
    raise RuntimeError(f"RISK_FAIL_CLOSED: {reason}")
