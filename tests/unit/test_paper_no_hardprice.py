"""Phase 3 — no hard-coded 42000 paper price, truthful quote validation."""
import pathlib

def test_no_42000_fallback_in_runtime():
    # Only production paths that assign price = 42000 are forbidden; comment example in manager is allowed but we ensure processes.py has none
    txt = pathlib.Path("src/gcis/runtime/processes.py").read_text()
    # must not contain assignment to 42000
    assert "price = 42000" not in txt
    assert "42000.0" not in txt.replace("# Phase 3: no fallback price — missing quote → NO_DATA, do not fabricate 42000", ""), "processes.py must not contain 42000 fallback"

def test_no_fallback_price_in_paper_execution():
    txt = pathlib.Path("src/gcis/execution/paper.py").read_text().lower()
    # paper.py must not contain fallback price logic
    assert "42000" not in txt
    assert "fallback" not in txt or "price" not in txt.split("fallback")[0][-100:]  # rough

def test_missing_quote_prevents_fill():
    from gcis.runtime.processes import _paper_tick
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    from gcis.persistence.models import Signal
    from datetime import datetime, timezone
    import gcis.persistence.db as db_mod

    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def fake_get_session():
        return Session()

    import unittest.mock as mock
    import gcis.runtime.processes as proc_mod

    # create a qualified signal but no LatestQuote
    s = Session()
    import uuid
    now = datetime.now(timezone.utc)
    sig = Signal(signal_id=str(uuid.uuid4()), venue="binance_um", symbol="BTCUSDT", direction="LONG", primary_timeframe="15m", state="QUALIFIED", strategy="ICT-A", entry=None, stop=None, target_1=None, target_2=None, setup_score=80, created_at=now)
    s.add(sig)
    s.commit()
    s.close()

    with mock.patch.object(db_mod, "get_session", fake_get_session):
        res = _paper_tick()
        # should not create position when quote missing → NO_DATA
        assert res.get("created", 0) == 0
        assert res.get("blocked") in (None, "NO_DATA") or res.get("created") == 0
        # verify no position created
        ss = Session()
        from gcis.persistence.models import Position
        assert ss.query(Position).count() == 0
        ss.close()

def test_stale_quote_prevents_fill():
    from gcis.runtime.processes import _paper_tick
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    from gcis.persistence.models import Signal, LatestQuote
    from datetime import datetime, timezone, timedelta
    from decimal import Decimal
    import gcis.persistence.db as db_mod
    import gcis.runtime.processes as proc_mod
    import unittest.mock as mock

    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def fake_get_session():
        return Session()

    # signal + stale quote (>5s)
    s = Session()
    import uuid
    now = datetime.now(timezone.utc)
    sig = Signal(signal_id=str(uuid.uuid4()), venue="binance_um", symbol="BTCUSDT", direction="LONG", primary_timeframe="15m", state="QUALIFIED", strategy="ICT-A", entry=None, stop=None, target_1=None, target_2=None, setup_score=80, created_at=now)
    s.add(sig)
    # stale quote 60s ago
    q = LatestQuote(symbol="BTCUSDT", venue="binance_um", price=Decimal("50000"), bid=Decimal("49999"), ask=Decimal("50001"), source="binance_um", updated_at=datetime.now(timezone.utc) - timedelta(seconds=60))
    s.add(q)
    s.commit()
    s.close()

    with mock.patch.object(db_mod, "get_session", fake_get_session):
        res = _paper_tick()
        ss = Session()
        from gcis.persistence.models import Position
        # stale should not create
        assert ss.query(Position).count() == 0
        ss.close()

def test_valid_quote_creates_fill():
    from gcis.runtime.processes import _paper_tick
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    from gcis.persistence.models import Signal, LatestQuote
    from datetime import datetime, timezone
    from decimal import Decimal
    import gcis.persistence.db as db_mod
    import gcis.runtime.processes as proc_mod
    import unittest.mock as mock

    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def fake_get_session():
        return Session()

    s = Session()
    import uuid
    now = datetime.now(timezone.utc)
    sig = Signal(signal_id=str(uuid.uuid4()), venue="binance_um", symbol="BTCUSDT", direction="LONG", primary_timeframe="15m", state="QUALIFIED", strategy="ICT-A", entry=None, stop=None, target_1=None, target_2=None, setup_score=80, created_at=now)
    s.add(sig)
    q = LatestQuote(symbol="BTCUSDT", venue="binance_um", price=Decimal("50100"), bid=Decimal("50099"), ask=Decimal("50101"), source="binance_um", updated_at=datetime.now(timezone.utc))
    s.add(q)
    s.commit()
    s.close()

    with mock.patch.object(db_mod, "get_session", fake_get_session):
        res = _paper_tick()
        ss = Session()
        from gcis.persistence.models import Position
        assert ss.query(Position).count() == 1
        pos = ss.query(Position).first()
        assert float(pos.entry_price) == 50100.0
        ss.close()
