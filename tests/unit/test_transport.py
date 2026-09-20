"""P03 transport tests: sharding, gap, polling, raw recorder, candle integrity, rotation."""
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd

def test_shard_streams():
    from gcis.data.transport.sharding import shard_streams, build_klines_streams, plan_shards, shard_summary
    streams = [f"s{i}@kline_1m" for i in range(400)]
    shards = shard_streams(streams, 180)
    assert len(shards) == 3
    assert len(shards[0]) == 180
    assert len(shards[1]) == 180
    assert len(shards[2]) == 40
    # plan
    symbols = [f"SYM{i}USDT" for i in range(400)]
    plan = plan_shards(symbols, focus_symbols=["BTCUSDT"], max_per_conn=180)
    assert len(plan["klines_1m"]) == 3  # 400/180
    summary = shard_summary(plan)
    assert summary["klines_1m"]["shards"] == 3
    assert summary["klines_1m"]["streams"] == 400

def test_ws_client_should_rotate():
    from gcis.data.transport.ws_client import WSConnection
    c = WSConnection(venue="binance_um", group="klines_1m-0", streams=["btcusdt@kline_1m"], ws_base="wss://fstream.binance.com", rotate_before_h=23)
    c.connected_at = time.time() - 23*3600 - 10
    assert c.should_rotate() is True
    c.connected_at = time.time() - 1*3600
    assert c.should_rotate() is False
    # URL
    url = c._build_url()
    assert "btcusdt@kline_1m" in url
    assert "stream?streams=" in url

def test_gap_detection():
    from gcis.data.transport.gap import detect_missing_intervals, backfill_missing
    # 1m interval us
    interval = 60_000*1000
    # times: 00:00, 00:01, 00:03 (missing 00:02)
    base = int(datetime(2024,1,1,0,0,tzinfo=timezone.utc).timestamp()*1_000_000)
    times = [base, base+interval, base+3*interval]
    gaps = detect_missing_intervals(times, base, base+5*interval, interval)
    # Should detect at least one gap containing 00:02
    assert len(gaps) >=1
    # No gap case
    times_ok = [base, base+interval, base+2*interval]
    gaps_ok = detect_missing_intervals(times_ok, base, base+3*interval, interval)
    assert gaps_ok == []

def test_polling_should_run():
    from gcis.data.transport.polling import polling_loop_should_run
    assert polling_loop_should_run("WEBSOCKET", 5, time.time()) is False
    assert polling_loop_should_run("DISCONNECTED", 5, None) is True
    assert polling_loop_should_run("DISCONNECTED", 5, time.time()-10) is True
    assert polling_loop_should_run("DISCONNECTED", 5, time.time()) is False
    assert polling_loop_should_run("DEGRADED", 5, time.time()-6) is True

def test_raw_recorder(tmp_path, monkeypatch):
    import gcis.data.recorder.store as rec
    monkeypatch.setattr(rec, "RAW_ROOT", tmp_path)
    payload = {"e":"kline","s":"BTCUSDT","k":{"t":1704067200000,"o":"100"}}
    p = rec.append_raw("binance_um","klines_1m", payload, ts_us=1704067200000*1000)
    assert p.exists()
    content = p.read_text()
    assert "BTCUSDT" in content
    assert "_received_at" in content
    files = rec.list_raw("binance_um", since_days=14)
    assert len(files) >=1
    # Purge not delete recent
    deleted = rec.purge_expired(retention_days=14)
    assert deleted == 0

def test_candle_persist_and_idempotent():
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    from gcis.data.transport.manager import handle_kline_message
    import asyncio
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    # Patch get_session to use this engine
    from unittest import mock
    SessionLocal = sessionmaker(bind=engine)
    # We need to patch gcis.persistence.db.get_session and manager's get_session import
    import gcis.persistence.db as db_mod
    import gcis.data.transport.manager as mgr_mod
    original_get_session = db_mod.get_session
    # create a function returning SessionLocal()
    def fake_get_session():
        return SessionLocal()
    # Patch both
    with mock.patch.object(db_mod, "get_session", fake_get_session), mock.patch.object(mgr_mod, "get_session", fake_get_session):
        # Also patch archive ingest to avoid filesystem
        with mock.patch("gcis.data.history.loader.ingest_rows_to_parquet", return_value=(Path("dummy"),1,"abc")):
            # Also patch ProviderStatus update side effect not needed
            payload = {
                "e": "kline",
                "E": 1704067260000,
                "s": "BTCUSDT",
                "k": {
                    "t": 1704067200000,
                    "T": 1704067259999,
                    "s": "BTCUSDT",
                    "i": "1m",
                    "o": "42100.0",
                    "c": "42150.0",
                    "h": "42200.0",
                    "l": "42000.0",
                    "v": "10.5",
                    "n": 100,
                    "x": True,
                    "q": "441000",
                }
            }
            # Run handle via asyncio
            asyncio.run(handle_kline_message(payload, received_at_us=1704067260000*1000, venue="binance_um"))
            # Check DB
            sess = SessionLocal()
            from gcis.persistence.models import Candle, EventOutbox
            candles = sess.query(Candle).all()
            assert len(candles) == 1
            c = candles[0]
            assert c.symbol == "BTCUSDT"
            assert c.venue == "binance_um"
            assert str(c.open) == "42100.000000000000000000" or "42100" in str(c.open)
            outs = sess.query(EventOutbox).all()
            assert len(outs) == 1
            assert outs[0].event_type == "candle.closed"
            # Second same payload should be idempotent (duplicate open_time)
            asyncio.run(handle_kline_message(payload, received_at_us=1704067260000*1000, venue="binance_um"))
            candles2 = sess.query(Candle).all()
            assert len(candles2) == 1  # still 1, deduped
            outs2 = sess.query(EventOutbox).all()
            # Second outbox not duplicated? Our code adds outbox per candle insert only when new, so still 1
            assert len(outs2) == 1
            sess.close()
    # restore not needed due to context

def test_transport_manager_plan():
    from gcis.data.transport.manager import TransportManager
    symbols = [f"SYM{i}USDT" for i in range(5)]
    focus = ["BTCUSDT"]
    mgr = TransportManager(venue="binance_um", symbols=symbols, focus_symbols=focus)
    mgr.build_connections()
    # klines 5 -> 1 shard, all_market 5*2+1=11 ->1 shard, focus 1*2=2 ->1 shard => total 3 connections
    assert len(mgr.connections) == 3
    health = mgr.health()
    assert health["ws_state"] in ("DISCONNECTED","WEBSOCKET","DEGRADED")
    assert health["plan"]["klines_1m"]["shards"] == 1
    assert health["plan"]["klines_1m"]["streams"] == 5

def test_no_business_logic_in_streamlit():
    # INV-21 check via file content scan already, but we also ensure transport not imported in app
    import pathlib
    txt = pathlib.Path("src/gcis/app/streamlit_app.py").read_text()
    assert "while True" not in txt
    assert "TransportManager" not in txt  # UI should not run transport directly
