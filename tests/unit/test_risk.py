from decimal import Decimal
from gcis.risk.manager import RiskManager
from gcis.risk.sizing import compute_quantity

def test_hard_cap_rejected():
    cfg={"risk":{"risk_per_trade_pct": 0.6, "max_daily_loss_pct":1.5, "max_trades_per_day":6}}
    rm=RiskManager(cfg)
    res=rm.check({"spread_bps":5}, {"risk_lock":"ACTIVE","trades_today":0,"current_equity":10000}, 0.0, False, {})
    assert not res["allowed"]
    assert "HARD_CAP" in res["reason_code"]

def test_sizing_rounds_down():
    qty=compute_quantity(equity=Decimal("10000"), risk_pct=Decimal("0.25"), entry=Decimal("50000"), stop=Decimal("49000"), fee_per_unit=Decimal("5"), slippage_per_unit=Decimal("5"), buffer_per_unit=Decimal("2"), step_size=Decimal("0.001"), min_qty=Decimal("0.001"), min_notional=Decimal("10"))
    assert qty>0
    # check step alignment
    assert (qty * 1000) % 1 == 0

def test_sizing_zero_if_notional():
    qty=compute_quantity(equity=Decimal("100"), risk_pct=Decimal("0.25"), entry=Decimal("50000"), stop=Decimal("49999"), fee_per_unit=Decimal("10"), slippage_per_unit=Decimal("10"), buffer_per_unit=Decimal("10"), step_size=Decimal("0.0001"), min_qty=Decimal("0.001"), min_notional=Decimal("1000"))
    assert qty==0

def test_daily_loss_lock():
    cfg={"risk":{"risk_per_trade_pct":0.25,"max_daily_loss_pct":1.5,"max_trades_per_day":6,"max_concurrent_positions":3,"max_open_worst_case_risk_pct":1.5,"max_per_symbol_risk_pct":0.5, "locks":{"max_spread_bps":15}}}
    rm=RiskManager(cfg)
    res=rm.check({"spread_bps":5}, {"risk_lock":"BLOCK_NEW_TRADES","trades_today":0,"current_equity":9850},0.0,False,{"open_positions":0})
    assert not res["allowed"]
    assert res["reason_code"]=="RISK_LIMIT"
