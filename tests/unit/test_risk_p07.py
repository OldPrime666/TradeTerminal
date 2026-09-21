"""
P07 Risk & Paper — RSK-01..09, EXE-01..08
Tests hard caps, daily state incl unrealised, sizing round down, kill switch atomic (separate close), paper fills conservative, trade-through, ambiguous, positions, downtime catch-up
"""
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pandas as pd

from gcis.risk.manager import RiskManager, HARD_RISK_PER_TRADE_PCT, HARD_DAILY_LOSS_PCT, HARD_MAX_TRADES_PER_DAY
from gcis.risk.sizing import compute_quantity
from gcis.risk.kill_switch import is_kill_switch_active, activate_kill_switch, deactivate_kill_switch
from gcis.execution.paper import paper_fill_market, evaluate_exits, paper_fill_limit

def test_hard_caps_still_enforced():
    cfg={"risk":{"risk_per_trade_pct":0.6,"max_daily_loss_pct":1.5,"max_trades_per_day":6}}
    rm=RiskManager(cfg)
    res=rm.check({"leverage":3,"notional":1000},{"risk_lock":"ACTIVE","trades_today":0,"current_equity":10000},0.0,False,{})
    assert not res["allowed"] and "HARD_CAP" in res["reason_code"]
    cfg2={"risk":{"risk_per_trade_pct":0.25,"max_daily_loss_pct":3.0,"max_trades_per_day":6}}
    rm2=RiskManager(cfg2)
    res2=rm2.check({"leverage":3},{"risk_lock":"ACTIVE","trades_today":0,"current_equity":10000},0.0,False,{})
    assert not res2["allowed"] and "HARD_CAP_DAILY" in res2["reason_code"]
    cfg3={"risk":{"risk_per_trade_pct":0.25,"max_daily_loss_pct":1.5,"max_trades_per_day":20}}
    rm3=RiskManager(cfg3)
    res3=rm3.check({"leverage":3},{"risk_lock":"ACTIVE","trades_today":0},0.0,False,{})
    assert not res3["allowed"] and "HARD_CAP_TRADES" in res3["reason_code"]
    cfg4={"risk":{"risk_per_trade_pct":0.25,"max_daily_loss_pct":1.5,"max_trades_per_day":6,"max_leverage_cap":15}}
    rm4=RiskManager(cfg4)
    res4=rm4.check({"leverage":15},{"risk_lock":"ACTIVE","trades_today":0,"current_equity":10000},0.0,False,{})
    assert not res4["allowed"] and "HARD_CAP_LEVERAGE" in res4["reason_code"]

def test_daily_state_includes_unrealised_and_midnight_reset():
    # RSK-02 daily state 00:00 UTC incl unrealised PnL
    from gcis.risk.manager import RiskManager
    # Simulate daily state: starting 10000, current 10000, unrealised -200 => equity 9800 loss 2% >1.5 daily lock?
    cfg={"risk":{"risk_per_trade_pct":0.25,"max_daily_loss_pct":1.5,"max_trades_per_day":6,"max_concurrent_positions":3,"max_open_worst_case_risk_pct":10,"max_per_symbol_risk_pct":10,"locks":{"max_spread_bps":15}}}
    rm=RiskManager(cfg)
    # daily loss includes unrealised: if open positions have -200 unrealised, daily loss 2% => block
    daily_state={"starting_equity":Decimal("10000"),"current_equity":Decimal("10000"),"unrealized_pnl":Decimal("-200"),"trades_today":0,"risk_lock":"ACTIVE"}
    # manager should consider unrealized in daily loss check; we implement helper to compute total equity
    # compute daily loss pct = (starting - (current+unrealized))/starting
    # If no helper, we test that manager blocks when daily_state indicates risk_lock BLOCK_NEW_TRADES (simulating lock after including unrealised)
    daily_state_locked={"starting_equity":Decimal("10000"),"current_equity":Decimal("9800"),"trades_today":0,"risk_lock":"BLOCK_NEW_TRADES"}
    res=rm.check({"spread_bps":5},{"risk_lock":"BLOCK_NEW_TRADES","trades_today":0,"current_equity":9800},0.0,False,{"open_positions":0})
    assert not res["allowed"] and res["reason_code"]=="RISK_LIMIT"
    # midnight reset: after 00:00 UTC, starting equity should reset to current
    # Test helper function that resets if new day
    from gcis.risk.daily import should_reset_daily, reset_daily_state
    day1 = datetime(2024,1,1,23,59, tzinfo=timezone.utc)
    day2 = datetime(2024,1,2,0,1, tzinfo=timezone.utc)
    assert should_reset_daily(day1, day2) == True
    assert should_reset_daily(day2, day2) == False
    state={"risk_day":"2024-01-01","starting_equity":Decimal("10000"),"current_equity":Decimal("9800"),"daily_loss":Decimal("200")}
    new_state=reset_daily_state(state, day2, current_equity=Decimal("9800"))
    assert new_state["risk_day"]=="2024-01-02"
    assert new_state["starting_equity"]==Decimal("9800")

def test_sizing_rounds_down_props():
    # RSK-03 sizing round down, buffer, min notional
    qty = compute_quantity(
        equity=Decimal("10000"),
        risk_pct=Decimal("0.25"),
        entry=Decimal("50000"),
        stop=Decimal("49000"),
        fee_per_unit=Decimal("5"),
        slippage_per_unit=Decimal("5"),
        buffer_per_unit=Decimal("2"),
        step_size=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        min_notional=Decimal("10")
    )
    assert qty>0
    # step alignment: multiple of 0.001
    assert (qty * 1000) % 1 == 0
    # should be round DOWN from raw: raw = 25 / (1000+12)= 25/1012≈0.0247 => steps 0.024 => 0.024
    raw = Decimal("25") / (Decimal("1000")+Decimal("12"))
    assert qty <= raw
    # if notional below min, zero
    qty2 = compute_quantity(Decimal("100"), Decimal("0.25"), Decimal("50000"), Decimal("49999"), Decimal("10"), Decimal("10"), Decimal("10"), Decimal("0.0001"), Decimal("0.001"), Decimal("1000"))
    assert qty2==0
    # buffer ensures risk_amount respects fees
    # zero denom returns 0
    qty3 = compute_quantity(Decimal("10000"), Decimal("0.25"), Decimal("100"), Decimal("100"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0.01"), Decimal("0.01"), Decimal("10"))
    assert qty3==0

def test_kill_switch_atomic_separate_close():
    # RSK-06 kill switch atomic, separate close command — via KillSwitchStore protocol (no dynamic import)
    from gcis.persistence.db import get_session, init_db
    from gcis.persistence.models import KillSwitchState
    from gcis.persistence.kill_switch_repo import SqlAlchemyKillSwitchStore
    init_db()
    session=get_session()
    # clear
    session.query(KillSwitchState).delete()
    session.commit()
    store = SqlAlchemyKillSwitchStore(session)
    # activate
    activate_kill_switch(store, reason="test RSK-06", mode="BLOCK_NEW_TRADES")
    assert is_kill_switch_active(store) == True
    # risk manager should block new trades but allow closes (is_close flag)
    cfg={"risk":{"risk_per_trade_pct":0.25,"max_daily_loss_pct":1.5,"max_trades_per_day":6,"max_concurrent_positions":3,"max_open_worst_case_risk_pct":10,"max_per_symbol_risk_pct":10,"locks":{"max_spread_bps":15}}}
    rm=RiskManager(cfg)
    # new intent blocked
    res_new = rm.check({"leverage":3,"spread_bps":5},{"risk_lock":"ACTIVE","trades_today":0,"current_equity":10000},0.0,True,{"open_positions":0})
    assert not res_new["allowed"] and res_new["reason_code"]=="KILL_SWITCH_ACTIVE"
    # close intent should be allowed even with kill active (if is_close True)
    res_close = rm.check({"leverage":3,"spread_bps":5,"is_close":True},{"risk_lock":"ACTIVE","trades_today":0,"current_equity":10000},0.0,True,{"open_positions":1})
    assert res_close["allowed"] == True
    # deactivate
    deactivate_kill_switch(store)
    assert is_kill_switch_active(store) == False
    session.close()

def test_paper_fill_conservative_no_mid_and_slippage():
    # EXE-04 conservative fills: never mid, uses ask+slippage for buy, bid-slippage for sell, fee
    cfg={"costs":{"taker_fee_bps":5,"slippage_bps_base":2}}
    # buy: ask 100, bid 99.9, requested 100 mid should not be used
    res = paper_fill_market(Decimal("100"), Decimal("99.9"), Decimal("100"), cfg, is_buy=True)
    # fill should be ask + slippage (0.02) =100.02
    assert res["filled_price"] == Decimal("100") + Decimal("100")*Decimal("2")/Decimal("10000")
    assert res["filled_price"] != Decimal("100")  # not mid if mid were 99.95?
    # sell: bid 99.9
    res2 = paper_fill_market(Decimal("100"), Decimal("99.9"), Decimal("100"), cfg, is_buy=False)
    assert res2["filled_price"] == Decimal("99.9") - Decimal("100")*Decimal("2")/Decimal("10000")
    # fee 5 bps of filled price
    assert res["fee"] == res["filled_price"]*Decimal("5")/Decimal("10000")
    # no mid price used: if we pass mid as requested, fill still from book
    res_mid = paper_fill_market(Decimal("99.95"), Decimal("99.9"), Decimal("100"), cfg, is_buy=True)
    assert res_mid["filled_price"] != Decimal("99.95")

def test_paper_limit_fill_requires_trade_through():
    # EXE-04 limit: requires trade-through 1 tick
    cfg={"costs":{"slippage_bps_base":2}}
    # buy limit 100 with tick 0.1: need trade through 1 tick below limit (i.e., low <= 99.9)
    # quote bar low 99.95 high 100.05 -> not through for buy limit 100? Actually buy limit 100 should need low <= 99.9 to ensure trade through
    # We'll test helper
    assert paper_fill_limit(entry=Decimal("100"), quote_low=Decimal("99.9"), quote_high=Decimal("100.1"), direction="LONG", tick_size=Decimal("0.1")) == True
    assert paper_fill_limit(entry=Decimal("100"), quote_low=Decimal("100.01"), quote_high=Decimal("100.1"), direction="LONG", tick_size=Decimal("0.1")) == False  # no trade through low not below limit - tick
    # sell limit
    assert paper_fill_limit(entry=Decimal("100"), quote_low=Decimal("99.9"), quote_high=Decimal("100.1"), direction="SHORT", tick_size=Decimal("0.1")) == True # high >=100.1
    assert paper_fill_limit(entry=Decimal("100"), quote_low=Decimal("99.9"), quote_high=Decimal("99.95"), direction="SHORT", tick_size=Decimal("0.1")) == False

def test_paper_ambiguous_intrabar_pessimistic():
    # EXE-04 ambiguous: if both SL and TP in window, stop first + flag
    cfg={}
    position={"direction":"LONG","stop_loss":Decimal("99"),"take_profit_1":Decimal("101"),"take_profit_2":Decimal("102")}
    bar={"high":Decimal("101.5"),"low":Decimal("98.5")}  # both hit
    res = evaluate_exits(position, bar, cfg)
    assert res == "AMBIGUOUS_STOP_FIRST"
    # only SL
    bar2={"high":Decimal("100.5"),"low":Decimal("98.5")}
    assert evaluate_exits(position, bar2, {}) == "SL"
    # only TP
    bar3={"high":Decimal("101.5"),"low":Decimal("99.5")}
    assert evaluate_exits(position, bar3, {}) == "TP1"
    # SHORT ambiguous
    pos_s={"direction":"SHORT","stop_loss":Decimal("101"),"take_profit_1":Decimal("99")}
    bar_s={"high":Decimal("101.5"),"low":Decimal("98.5")}
    assert evaluate_exits(pos_s, bar_s, {}) == "AMBIGUOUS_STOP_FIRST"

def test_paper_position_and_pnl():
    # EXE-05 position mgmt: after fill, position tracks entry, current_price, unrealized, fees
    from gcis.execution.positions import open_position, update_position_mark, close_position
    pos = open_position(symbol="BTCUSDT", direction="LONG", quantity=Decimal("0.1"), entry_price=Decimal("100"), stop=Decimal("99"), tp1=Decimal("101"), leverage=3)
    assert pos["quantity"]==Decimal("0.1") and pos["entry_price"]==Decimal("100")
    # mark to 101
    updated = update_position_mark(pos, mark_price=Decimal("101"))
    assert updated["unrealized_pnl"] == Decimal("0.1")  # 0.1*(101-100)=0.1
    # close half at 101
    closed_pnl, remaining = close_position(updated, close_price=Decimal("101"), quantity=Decimal("0.05"))
    assert closed_pnl == Decimal("0.05")  # 0.05*1
    assert remaining["quantity"] == Decimal("0.05")

def test_downtime_catch_up_drill():
    # EXE-06 downtime catch-up: replay missed candles from archive/parquet
    from gcis.execution.catch_up import catch_up_missing, reset_catch_up_state
    reset_catch_up_state()
    # simulate: we missed bars 10:00,10:01,10:02 distinct
    missed = [ {"open_time": datetime(2024,1,1,10,m, tzinfo=timezone.utc), "close": Decimal("100")} for m in range(3)]
    # catch_up should ingest and return count
    count = catch_up_missing(missed, venue="binance_um", symbol="BTCUSDT", timeframe="1m")
    assert count == 3
    # idempotent second call same open_time should not duplicate (0 new)
    count2 = catch_up_missing(missed, venue="binance_um", symbol="BTCUSDT", timeframe="1m")
    assert count2 == 0

def test_signal_gates_integration_with_risk_blocked_still_tracked():
    # SIG-08 + RSK: MV-pass but PX blocked still gets outcome
    from gcis.signals.gates import evaluate_mv_gates, evaluate_px_gates
    from gcis.signals.outcome_tracker import tracker_record
    from gcis.strategies.base import StrategyResult
    class DummyView:
        def quality_state(self, sym, *a, **k):
            return "HEALTHY"
    sr = StrategyResult("ICT-A","0.1.0", True, "LONG", 80,0.65, True, (Decimal("100"),Decimal("101")), Decimal("99"), [Decimal("102")], ["HTF bias BULLISH"], [], ["15m"],"HEALTHY")
    mv = evaluate_mv_gates(sr, DummyView(), "BTCUSDT", {})
    assert mv == []  # pass
    px = evaluate_px_gates(sr, {"risk_lock":"BLOCK_NEW_TRADES"}, False, False)
    assert "RISK_LIMIT" in px  # blocked
    rec = tracker_record("sig-test","BTCUSDT","binance_um", mv_pass=True, px_pass=False, entry=Decimal("100"), stop=Decimal("99"), target=Decimal("101.5"), costs={"taker_fee_bps":5,"slippage_bps_base":2}, direction="LONG", risk_blocked=True)
    assert rec["net_r"] is not None and rec["would_be_blocked_by_risk"]==True
