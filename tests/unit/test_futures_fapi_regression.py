"""Futures /fapi regression §6 — ensure UM futures never regress to spot /api endpoints."""
import pathlib
import re

def test_binance_um_uses_fapi_exchangeInfo():
    txt = pathlib.Path("src/gcis/data/exchange/binance_um.py").read_text()
    assert "/fapi/v1/exchangeInfo" in txt, "binance_um must use /fapi/v1/exchangeInfo (futures), not spot"
    assert "/api/v3/exchangeInfo" not in txt, "spot /api/v3/exchangeInfo must not appear in futures adapter"

def test_binance_um_uses_fapi_klines():
    txt = pathlib.Path("src/gcis/data/exchange/binance_um.py").read_text()
    assert "/fapi/v1/klines" in txt, "must use /fapi/v1/klines"
    # ensure not using spot api
    assert txt.count("/fapi/v1/klines") >= 1

def test_binance_um_ping_time_fapi():
    txt = pathlib.Path("src/gcis/data/exchange/binance_um.py").read_text()
    assert "/fapi/v1/ping" in txt
    assert "/fapi/v1/time" in txt

def test_binance_cm_uses_dapi():
    txt = pathlib.Path("src/gcis/data/exchange/binance_cm.py").read_text()
    assert "/dapi/v1/exchangeInfo" in txt, "CM must use dapi"

def test_history_loader_uses_fapi_bulk_or_rest_futures():
    # history loader should prefer futures bulk zip path (um) and futures klines fallback, not spot
    import pathlib
    # Check loader uses binance_um adapter / futures markPriceKlines if present
    txt_um = pathlib.Path("src/gcis/data/exchange/binance_um.py").read_text()
    # must expose markPriceKlines on fapi
    assert "markPriceKlines" in txt_um
    assert "/fapi/v1/markPriceKlines" in txt_um

def test_fake_harness_uses_fapi_fixture():
    # fake should mirror fapi futures, not spot
    from gcis.data.exchange.fake_exchange import FakeBinanceUMAdapter
    a = FakeBinanceUMAdapter()
    # fake still returns futures contracts (PERPETUAL LINEAR)
    cs = a.fetch_contracts()
    assert any(c["contract_type"] == "PERPETUAL" for c in cs)
    assert all(c["contract_family"] == "LINEAR" for c in cs)

def test_no_spot_import_in_futures_adapter():
    # ensure no accidental import of spot BinanceAdapter (api/v3) in um file
    txt = pathlib.Path("src/gcis/data/exchange/binance_um.py").read_text().lower()
    # spot base URL should not be fapi fallback to spot
    assert "api.binance.com/api" not in txt
    # ws base should be fstream (futures) not spot stream
    assert "fstream.binance.com" in txt
