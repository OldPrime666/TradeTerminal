"""P02 historical bulk tests: bulk parsing, parquet archive, HTF derived, gap report, idempotency."""
import io
import csv
import zipfile
import hashlib
import tempfile
from pathlib import Path
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import pandas as pd

def _make_fake_binance_zip(rows: list[list[str]]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        # csv inside
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf)
        for r in rows:
            writer.writerow(r)
        z.writestr("BTCUSDT-1m-2024-01-01.csv", csv_buf.getvalue())
    return bio.getvalue()

def test_parse_binance_kline_csv_row():
    from gcis.data.history.bulk import parse_binance_kline_csv_row
    row = ["1704067200000","42100.1","42150.0","42090.0","42120.0","123.4","1704067259999","5200000","1000","60","2500000","0"]
    parsed = parse_binance_kline_csv_row(row)
    assert parsed is not None
    # open_time ms -> us
    assert parsed["open_time"] == 1704067200000 * 1000
    assert parsed["open"] == "42100.1"
    assert parsed["trade_count"] == 1000

def test_normalize_timestamp_to_us():
    from gcis.data.archive.store import normalize_timestamp_to_us
    assert normalize_timestamp_to_us(1704067200) == 1704067200 * 1_000_000  # seconds
    assert normalize_timestamp_to_us(1704067200000) == 1704067200000 * 1000  # ms
    assert normalize_timestamp_to_us(1704067200000000) == 1704067200000000  # us

def test_archive_write_read_idempotent(tmp_path, monkeypatch):
    # Override ARCHIVE_ROOT to tmp
    import gcis.data.archive.store as store
    monkeypatch.setattr(store, "ARCHIVE_ROOT", tmp_path)
    from gcis.data.history.loader import ingest_rows_to_parquet
    from gcis.data.archive.store import archive_path, read_parquet, df_from_bulk_rows
    rows = [
        {"open_time": 1704067200000*1000, "open":"100","high":"110","low":"90","close":"105","volume":"10","close_time":1704067259999*1000, "quote_volume":"1050","trade_count":10,"taker_buy_volume":"5"},
        {"open_time": 1704067260000*1000, "open":"105","high":"115","low":"95","close":"110","volume":"12","close_time":1704067319999*1000, "quote_volume":"1320","trade_count":11,"taker_buy_volume":"6"},
    ]
    path, cnt, sha = ingest_rows_to_parquet("binance_um","BTCUSDT","1m", rows, date_str="2024-01-01")
    assert cnt == 2
    assert path.exists()
    # read back
    df = read_parquet(path)
    assert len(df) == 2
    # second ingest identical should be idempotent (skip rewrite, same sha)
    path2, cnt2, sha2 = ingest_rows_to_parquet("binance_um","BTCUSDT","1m", rows, date_str="2024-01-01")
    assert cnt2 == 2
    assert sha == sha2
    # Adding duplicate row should deduplicate
    rows_dup = rows + [rows[0]]
    path3, cnt3, sha3 = ingest_rows_to_parquet("binance_um","BTCUSDT","1m", rows_dup, date_str="2024-01-01")
    assert cnt3 == 2  # deduplicated

def test_bulk_download_range_with_mock(monkeypatch, tmp_path):
    """Test download_range with mocked httpx zip response (offline CODE_VERIFIED)."""
    import gcis.data.history.bulk as bulk
    # Create fake zip for 2 days
    rows_day1 = [
        ["1704067200000","42100","42200","42000","42150","10","1704067259999","421500","100","5","210000","0"],
        ["1704067260000","42150","42250","42100","42200","11","1704067319999","464200","101","6","253200","0"],
    ]
    rows_day2 = [
        ["1704153600000","42200","42300","42100","42250","9","1704153659999","380000","99","4","168000","0"],
    ]
    zip1 = _make_fake_binance_zip(rows_day1)
    zip2 = _make_fake_binance_zip(rows_day2)
    # Map URL to zip bytes
    def fake_get(self, url, *args, **kwargs):
        class Resp:
            def __init__(self, content, status_code=200):
                self.content = content
                self.status_code = status_code
                # do not decode binary zip
                try:
                    self.text = content.decode(errors="ignore") if isinstance(content, bytes) else ""
                except Exception:
                    self.text = ""
            def raise_for_status(self):
                if self.status_code >=400:
                    import httpx
                    raise httpx.HTTPStatusError(f"{self.status_code}", request=None, response=self)
        if url.endswith(".CHECKSUM"):
            # no checksum
            return Resp(b"", status_code=404)
        if "2024-01-01.zip" in url:
            return Resp(zip1, 200)
        if "2024-01-02.zip" in url:
            return Resp(zip2, 200)
        return Resp(b"", status_code=404)
    monkeypatch.setattr("httpx.Client.get", fake_get)
    # Also need to patch sha verification to avoid file read?
    rows = bulk.download_range("BTCUSDT","1m", start=date(2024,1,1), end=date(2024,1,2), market="um", timeout=5)
    assert len(rows) == 3
    assert rows[0]["open_time"] == 1704067200000*1000
    assert rows[1]["open_time"] == 1704067260000*1000
    assert rows[2]["open_time"] == 1704153600000*1000
    # Ensure chronological sorted
    assert rows == sorted(rows, key=lambda x: x["open_time"])

def test_quality_report_gap():
    from gcis.data.quality.report import quality_report
    import pandas as pd
    from datetime import timezone
    # Make df with 2 bars but gap of 2 missing (1m interval)
    rows = [
        {"open_time": pd.Timestamp("2024-01-01 00:00:00+00:00"), "open":"100","high":"110","low":"90","close":"105","volume":"10","close_time":pd.Timestamp("2024-01-01 00:00:59+00:00"), "quote_volume":"1050","trade_count":10,"taker_buy_volume":"5"},
        {"open_time": pd.Timestamp("2024-01-01 00:03:00+00:00"), "open":"106","high":"116","low":"96","close":"111","volume":"12","close_time":pd.Timestamp("2024-01-01 00:03:59+00:00"), "quote_volume":"1320","trade_count":11,"taker_buy_volume":"6"},
    ]
    df = pd.DataFrame(rows)
    report = quality_report("binance_um","BTCUSDT","1m", df)
    assert report["gap_count"] >=1
    # status could be GAP or INSUFFICIENT_HISTORY (since <300 bars). Check gap_count is key for DAT-14
    assert report["gap_count"] >=1
    assert report["status"] in ("GAP","INSUFFICIENT_HISTORY")
    # No gap case
    rows_ok = [
        {"open_time": pd.Timestamp("2024-01-01 00:00:00+00:00"), "open":"100","high":"110","low":"90","close":"105","volume":"10","close_time":pd.Timestamp("2024-01-01 00:00:59+00:00"), "quote_volume":"1050","trade_count":10,"taker_buy_volume":"5"},
        {"open_time": pd.Timestamp("2024-01-01 00:01:00+00:00"), "open":"105","high":"115","low":"95","close":"110","volume":"12","close_time":pd.Timestamp("2024-01-01 00:01:59+00:00"), "quote_volume":"1320","trade_count":11,"taker_buy_volume":"6"},
    ]
    df2 = pd.DataFrame(rows_ok)
    report2 = quality_report("binance_um","BTCUSDT","1m", df2)
    assert report2["gap_count"] == 0
    assert report2["status"] in ("OK","INSUFFICIENT_HISTORY")  # less than 300 bars -> insufficient

def test_derive_timeframe():
    from gcis.data.archive.store import derive_timeframe
    import pandas as pd
    # 3 consecutive 1m bars -> 1x 5m? Actually need 5 bars for 5m
    base = pd.Timestamp("2024-01-01 00:00:00+00:00")
    rows = []
    for i in range(5):
        rows.append({
            "open_time": base + pd.Timedelta(minutes=i),
            "open": str(100+i),
            "high": str(110+i),
            "low": str(90+i),
            "close": str(105+i),
            "volume": str(10+i),
            "quote_volume": str(1000+i*100),
            "trade_count": 10+i,
            "taker_buy_volume": str(5+i),
            "close_time": base + pd.Timedelta(minutes=i, seconds=59)
        })
    df = pd.DataFrame(rows)
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], utc=True)
    # Ensure numeric columns for agg
    for col in ["open","high","low","close","volume","quote_volume","trade_count","taker_buy_volume"]:
        df[col] = pd.to_numeric(df[col])
    derived = derive_timeframe(df, "5m")
    assert len(derived) == 1
    assert derived.iloc[0]["open"] == 100
    assert derived.iloc[0]["close"] == 109  # last close 105+4
    assert derived.iloc[0]["high"] == 114  # max high 110+4
    assert derived.iloc[0]["low"] == 90

def test_loader_bulk_and_tail_idempotent(monkeypatch, tmp_path):
    """Test download_history orchestrator with mocked bulk + mocked REST tail (offline)."""
    import gcis.data.archive.store as store
    monkeypatch.setattr(store, "ARCHIVE_ROOT", tmp_path)
    import gcis.data.history.loader as loader
    # mock bulk rows for BTCUSDT 1m — patch loader's imported download_range
    fake_rows = [
        {"open_time": 1704067200000*1000, "open":"100","high":"110","low":"90","close":"105","volume":"10","close_time":1704067259999*1000, "quote_volume":"1050","trade_count":10,"taker_buy_volume":"5"},
    ]
    monkeypatch.setattr(loader, "load_from_bulk", lambda *a, **kw: {"venue":"binance_um","symbol":"BTCUSDT","timeframe":"1m","rows":1,"written":[{"date":"2024-01-01","path":str(tmp_path/"binance_um/BTCUSDT/1m/2024-01-01.parquet"),"rows":1}],"quality":{"status":"OK"},"status":"OK"})
    # also need to ensure download_range not called; we stub load_from_bulk
    # mock tail to return empty (no extra)
    monkeypatch.setattr(loader, "load_from_rest_tail", lambda *a, **kw: {"status":"OK","rows":0,"written":[]})
    # Also need to mock DB segment writer to avoid needing DB
    monkeypatch.setattr(loader, "_ensure_archive_segment", lambda *a, **kw: None)
    # Actually test the ingest directly via load_from_bulk stub, but to test idempotency we call ingest manually
    from gcis.data.history.loader import ingest_rows_to_parquet
    path, cnt, sha = ingest_rows_to_parquet("binance_um","BTCUSDT","1m", fake_rows, date_str="2024-01-01")
    assert cnt == 1
    assert path.exists()
    # second ingest identical should be idempotent via same path
    path2, cnt2, sha2 = ingest_rows_to_parquet("binance_um","BTCUSDT","1m", fake_rows, date_str="2024-01-01")
    assert cnt2 == 1
    assert sha == sha2
    # Now test download_history orchestrator with patched load_from_bulk
    res = loader.download_history(symbols=["BTCUSDT"], venue="binance_um", timeframe="1m", start="2024-01-01", end="2024-01-01")
    assert "BTCUSDT" in res["symbols"]

def test_loader_uses_registry_when_symbols_none(monkeypatch, tmp_path):
    """When symbols None, loader pulls from ContractRegistry TRADING."""
    import gcis.data.archive.store as store
    monkeypatch.setattr(store, "ARCHIVE_ROOT", tmp_path)
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    from gcis.persistence.models import ContractRegistry
    from datetime import datetime, timezone
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    sess = SessionLocal()
    # insert 2 contracts
    for sym in ["BTCUSDT","ETHUSDT"]:
        cr = ContractRegistry(contract_id=f"binance_um:{sym}", venue="binance_um", symbol=sym, base=sym.replace("USDT",""), quote="USDT", settle_asset="USDT", contract_family="LINEAR", contract_type="PERPETUAL", status="TRADING", asset_class="CRYPTO", first_seen=datetime.now(timezone.utc))
        sess.add(cr)
    sess.commit()
    # patch get_session to return our in-memory session factory that yields same engine? easier: patch loader's get_session
    import gcis.data.history.loader as loader
    # mock bulk to avoid network
    import gcis.data.history.bulk as bulk
    fake_rows = [{"open_time":1704067200000*1000,"open":"1","high":"2","low":"0.5","close":"1.5","volume":"10","close_time":1704067259999*1000, "quote_volume":"15","trade_count":5,"taker_buy_volume":"6"}]
    monkeypatch.setattr(bulk, "download_range", lambda *a, **kw: fake_rows)
    monkeypatch.setattr(loader, "load_from_rest_tail", lambda *a, **kw: {"status":"OK","rows":0,"written":[]})
    monkeypatch.setattr(loader, "_ensure_archive_segment", lambda *a,**kw: None)
    # patch get_session inside loader
    monkeypatch.setattr("gcis.data.history.loader.get_session", lambda: sess)
    res = loader.download_history(symbols=None, venue="binance_um", timeframe="1m", start="2024-01-01", end="2024-01-01")
    # Should have resolved 2 symbols from registry but we limit to 20; check both present?
    # Our loader default limit 20, so both should be attempted, but we mock download_range always returns same row for each symbol -> should have both keys
    assert "BTCUSDT" in res["symbols"]
    assert "ETHUSDT" in res["symbols"]
    sess.close()
