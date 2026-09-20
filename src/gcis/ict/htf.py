"""
ICT-10 HTF / LTF conflict — NO_TRADE policy
Config: htf_ltf_conflict_policy NO_TRADE

Definition:
  HTF bias (from higher timeframe structure, e.g., 1h or 4h) must align with LTF signal direction.
  If HTF bias is BULLISH, only LONG allowed; if BEARISH only SHORT.
  If UNDEFINED, no trade? Or allows both? Spec says NO_TRADE on conflict, so UNDEFINED is not conflict.

  Inputs: htf_bias (BULLISH/BEARISH/UNDEFINED), ltf_direction (LONG/SHORT), policy cfg

  If policy NO_TRADE and conflict → block (return False, reason HTF_LTF_CONFLICT).

Causal: bias computed causally from closed HTF bars.
"""
from typing import Tuple

def check_htf_ltf_alignment(htf_bias: str, ltf_direction: str, cfg: dict = None) -> Tuple[bool, str]:
    if cfg is None:
        cfg = {}
    policy = cfg.get("htf_ltf_conflict_policy", "NO_TRADE")
    if policy != "NO_TRADE":
        return (True, "NO_POLICY")
    if htf_bias == "UNDEFINED" or htf_bias is None:
        return (True, "HTF_UNDEFINED")
    if ltf_direction is None:
        return (True, "NO_DIRECTION")
    if htf_bias == "BULLISH" and ltf_direction == "LONG":
        return (True, "ALIGNED")
    if htf_bias == "BEARISH" and ltf_direction == "SHORT":
        return (True, "ALIGNED")
    if htf_bias == "BULLISH" and ltf_direction == "SHORT":
        return (False, "HTF_LTF_CONFLICT_BULL_VS_SHORT")
    if htf_bias == "BEARISH" and ltf_direction == "LONG":
        return (False, "HTF_LTF_CONFLICT_BEAR_VS_LONG")
    return (True, "ALIGNED")
