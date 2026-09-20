from gcis.signals.lifecycle import can_transition, compute_expiry
from datetime import datetime, timezone

def test_illegal_transition():
    assert not can_transition("EXECUTED","QUALIFIED")
    assert not can_transition("DISCOVERED","EXECUTED")
    assert can_transition("DISCOVERED","QUALIFIED")
    assert can_transition("ARMED","TRIGGERED")
    assert can_transition("BLOCKED","QUALIFIED")

def test_expiry():
    cfg={"signal":{"ttl_bars":{"15m":8}}}
    now=datetime.now(timezone.utc)
    exp=compute_expiry(now,"15m",cfg)
    assert (exp-now).total_seconds()==8*15*60
