"""Fake exchange harness §43 — offline deterministic, free-only, never hits network."""

def test_fake_binance_um_contracts_from_fixture():
    from gcis.data.exchange.fake_exchange import FakeBinanceUMAdapter
    a = FakeBinanceUMAdapter()
    contracts = a.fetch_contracts()
    assert len(contracts) == 5
    btc = next(c for c in contracts if c["symbol"] == "BTCUSDT")
    assert btc["contract_family"] == "LINEAR"
    assert btc["status"] == "TRADING"

def test_fake_bybit_contracts():
    from gcis.data.exchange.fake_exchange import FakeBybitAdapter
    a = FakeBybitAdapter()
    assert len(a.fetch_contracts()) >= 3

def test_fake_okx_hyperliquid():
    from gcis.data.exchange.fake_exchange import FakeOKXAdapter, FakeHyperliquidAdapter
    assert len(FakeOKXAdapter().fetch_contracts()) >= 2
    assert len(FakeHyperliquidAdapter().fetch_contracts()) >= 4

def test_fake_klines_deterministic():
    from gcis.data.exchange.fake_exchange import FakeBinanceUMAdapter
    a = FakeBinanceUMAdapter()
    k1 = a.klines("BTCUSDT", "1m", limit=5, startTime=1700000000000)
    k2 = a.klines("BTCUSDT", "1m", limit=5, startTime=1700000000000)
    assert k1 == k2
    # different symbol yields different prices
    k_eth = a.klines("ETHUSDT", "1m", limit=5, startTime=1700000000000)
    assert k_eth[0][4] != k1[0][4]
    # structure 12 fields
    assert len(k1[0]) == 12

def test_fake_klines_limit_cap():
    from gcis.data.exchange.fake_exchange import FakeBinanceUMAdapter
    a = FakeBinanceUMAdapter()
    k = a.klines("BTCUSDT", "1m", limit=2000)
    assert len(k) == 1500

def test_fake_ws_harness_deterministic():
    from gcis.data.exchange.fake_exchange import FakeWSHarness
    h1 = FakeWSHarness(["BTCUSDT"], venue="binance_um")
    h2 = FakeWSHarness(["BTCUSDT"], venue="binance_um")
    # stream produces bookTicker then kline alternating, but prices deterministic per symbol
    p1, _ = next(iter(h1.stream(2)))
    p2, _ = next(iter(h2.stream(2)))
    # both first payload is bookTicker for BTCUSDT — same price
    assert p1["s"] == p2["s"] == "BTCUSDT"
    assert p1["b"] == p2["b"]
    assert p1["a"] == p2["a"]

def test_fake_get_adapter_factory():
    from gcis.data.exchange.fake_exchange import get_fake_adapter
    for venue in ["binance_um", "bybit_linear", "okx_swap", "hyperliquid", "gate_linear"]:
        a = get_fake_adapter(venue)
        assert a.ping() is True
        assert a.get_time() > 0
        assert len(a.fetch_contracts()) >= 1

def test_fake_ws_feeds_transport_handlers():
    import asyncio
    from gcis.data.exchange.fake_exchange import FakeWSHarness
    from gcis.data.transport.manager import handle_kline_message, handle_bookticker_message
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    import gcis.persistence.db as db_mod
    import gcis.data.transport.manager as mgr_mod
    import unittest.mock as mock

    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def fake_get_session():
        return SessionLocal()

    async def _run():
        h = FakeWSHarness(["BTCUSDT", "ETHUSDT"], venue="binance_um")
        for payload, ts in h.stream(4):
            if "k" in payload:
                await handle_kline_message(payload, ts, venue="binance_um")
            else:
                await handle_bookticker_message(payload, ts, venue="binance_um")
        # verify at least one quote persisted
        s = fake_get_session()
        from gcis.persistence.models import LatestQuote, Candle
        assert s.query(LatestQuote).count() >= 1
        # at least one candle (kline)
        assert s.query(Candle).count() >= 1
        s.close()

    with mock.patch.object(db_mod, "get_session", fake_get_session), mock.patch.object(mgr_mod, "get_session", fake_get_session):
        asyncio.run(_run())
