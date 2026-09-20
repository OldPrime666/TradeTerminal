from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional

def paper_fill_market(requested_price: Decimal, bid: Decimal, ask: Decimal, config: dict, is_buy: bool) -> dict:
    """
    Conservative paper fill: never mid price. Market orders walk fresh book when available else best bid/ask + slippage.
    """
    slippage_bps = Decimal(str(config.get("costs",{}).get("slippage_bps_base",2)))
    # slippage as bps of price
    slippage = requested_price * slippage_bps / Decimal(10000)
    if is_buy:
        # buyer pays ask + slippage
        fill = (ask if ask else requested_price) + slippage
    else:
        fill = (bid if bid else requested_price) - slippage
    fee_bps = Decimal(str(config.get("costs",{}).get("taker_fee_bps",10)))
    fee = fill * fee_bps / Decimal(10000)
    return {"filled_price": fill, "fee": fee, "slippage": slippage}

def evaluate_exits(position: dict, quote_bar: dict, config: dict) -> Optional[str]:
    """
    Evaluate stops/targets on QuoteBar window extremes.
    If stop and target both in window → pessimistic (stop first) + flag AMBIGUOUS_INTRABAR_PATH
    """
    # position: entry, stop, tp1, tp2
    # quote_bar: high, low, close
    high = quote_bar.get("high")
    low = quote_bar.get("low")
    stop = position.get("stop_loss")
    tp1 = position.get("take_profit_1")
    tp2 = position.get("take_profit_2")
    # for LONG positions
    direction = position.get("direction", "LONG")
    # LONG: stop below, target above
    hit_stop = low <= stop if stop and low is not None else False
    hit_tp1 = high >= tp1 if tp1 and high is not None else False
    hit_tp2 = high >= tp2 if tp2 and high is not None else False
    if direction == "SHORT":
        hit_stop = high >= stop if stop and high is not None else False
        hit_tp1 = low <= tp1 if tp1 and low is not None else False
    if hit_stop and hit_tp1:
        return "AMBIGUOUS_STOP_FIRST"
    if hit_stop:
        return "SL"
    if hit_tp1:
        return "TP1"
    if hit_tp2:
        return "TP2"
    return None
