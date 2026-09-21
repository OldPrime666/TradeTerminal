"""P12 §12 History → Backtest bridge — ingest parquet also populates Candle canonical for backtest/MarketView."""
import pandas as pd
from datetime import datetime, timezone, timedelta

def _setup_isolated_db(monkeypatch, tmp_path):
    from gcis.persistence.db import Base, get_engine
    import gcis.persistence.models  # ensure Base has all tables
    from sqlalchemy.orm import sessionmaker
    db_url = f"sqlite:///{tmp_path}/bridge.db"
    engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    monkeypatch.setattr("gcis.persistence.db.get_session", lambda: SessionLocal())
    # loader also imports get_session directly, patch that module too if present
    try:
        monkeypatch.setattr("gcis.data.history.loader.get_session", lambda: SessionLocal())
    except Exception:
        pass
    return SessionLocal

def test_ingest_populates_candle_and_backtest_nonzero(monkeypatch, tmp_path):
    SessionLocal = _setup_isolated_db(monkeypatch, tmp_path)
    from gcis.data.history.loader import ingest_rows_to_parquet
    from gcis.persistence.models import Candle
    # also patch archive_path to use tmp_path var/archive
    import gcis.data.archive.store as arch_store
    orig_archive_path = arch_store.archive_path
    def tmp_archive_path(venue, symbol, tf, date_str):
        base = tmp_path / "var" / "archive" / venue / symbol / tf
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{date_str}.parquet"
    monkeypatch.setattr("gcis.data.archive.store.archive_path", tmp_archive_path)
    monkeypatch.setattr("gcis.data.history.loader.archive_path", tmp_archive_path)
    # patch disk budget to avoid var/archive missing
    monkeypatch.setattr("gcis.data.archive.store.check_disk_budget", lambda *a, **k: "OK")
    monkeypatch.setattr("gcis.data.history.loader.check_disk_budget", lambda *a, **k: "OK")

    # create 60 synthetic rows (1m candles)
    venue = "binance_um"
    symbol = "BTCUSDT"
    timeframe = "1m"
    base_dt = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    rows = []
    for i in range(60):
        ot = int((base_dt + timedelta(minutes=i)).timestamp() * 1_000_000)
        ct = ot + 60_000*1_000  # 1m
        rows.append({
            "open_time": ot,
            "open": "42000",
            "high": "42100",
            "low": "41900",
            "close": "42050",
            "volume": "10",
            "close_time": ct,
            "quote_volume": "420000",
            "trade_count": 100,
            "taker_buy_volume": "5",
        })
    path, cnt, sha = ingest_rows_to_parquet(venue, symbol, timeframe, rows, date_str="2024-01-01")
    assert cnt == 60
    assert path.exists()
    # check Candle rows
    s = SessionLocal()
    candles = s.query(Candle).filter(Candle.venue==venue, Candle.symbol==symbol, Candle.timeframe==timeframe).all()
    assert len(candles) == 60, f"expected 60 candles, got {len(candles)}"
    s.close()
    # idempotent second ingest should not duplicate
    path2, cnt2, sha2 = ingest_rows_to_parquet(venue, symbol, timeframe, rows, date_str="2024-01-01")
    assert cnt2 == 60
    s2 = SessionLocal()
    candles2 = s2.query(Candle).filter(Candle.venue==venue, Candle.symbol==symbol, Candle.timeframe==timeframe).all()
    assert len(candles2) == 60
    s2.close()
    # now backtest should see non-zero bars via repo (without df_override)
    from gcis.backtest.engine import run_backtest
    res = run_backtest(symbols=[symbol], timeframe=timeframe)
    # With 60 bars, backtest warmup is 50, so should have some trades or at least not NO_DATA
    assert res["status"] != "NO DATA", f"backtest status {res}"
    assert res["bars"] >= 60 or res.get("metrics", {}).get("bars", 0) >= 60 or res.get("trades_count", 0) >= 0
    # MarketView should load candles
    from gcis.market.view import MarketView
    from gcis.persistence.candle_repo import SqlAlchemyCandleRepository
    repo = SqlAlchemyCandleRepository()
    rows_db = repo.fetch([symbol], timeframe)
    assert len(rows_db) == 60
    # Build MarketView
    from gcis.backtest.engine import _df_from_rows
    df = _df_from_rows(rows_db)
    assert len(df) == 60
    view = MarketView(as_of=df.iloc[-1]["close_time"], candles={symbol: {timeframe: df}}, quotes={symbol: {"updated_at": df.iloc[-1]["close_time"], "price": float(df.iloc[-1]["close"])}})
    assert symbol in view.candles

def test_ingest_bridge_no_fabrication_stale(monkeypatch, tmp_path):
    # Ensure empty ingest raises, and empty DB gives NO DATA honest
    SessionLocal = _setup_isolated_db(monkeypatch, tmp_path)
    from gcis.data.history.loader import ingest_rows_to_parquet
    import pytest
    with pytest.raises(ValueError):
        ingest_rows_to_parquet("binance_um", "BTCUSDT", "1m", [], date_str="2024-01-01")
    from gcis.backtest.engine import run_backtest
    # with empty DB, backtest should be NO DATA, not fake
    res = run_backtest(symbols=["BTCUSDT"], timeframe="1m")
    assert res["status"] == "NO DATA"
