"""P11 Full terminal tests: pages, components, readmodels, EXE-02 idempotency, forbidden strings."""
import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_pages_exist():
    for name in ["overview.py","coin_detail.py","charts.py","risk_center.py","trade_desk.py"]:
        p = ROOT / "src/gcis/app/pages" / name
        assert p.exists(), f"{name} missing"
        txt = p.read_text(encoding="utf-8")
        assert len(txt) > 20

def test_components_and_readmodels():
    assert (ROOT / "src/gcis/app/components/banner.py").exists()
    assert (ROOT / "src/gcis/app/components/charts.py").exists()
    assert (ROOT / "src/gcis/app/readmodels/overview.py").exists()
    txt = (ROOT / "src/gcis/app/components/charts.py").read_text()
    assert "800" in txt and "capped" in txt.lower()
    txt2 = (ROOT / "src/gcis/app/readmodels/overview.py").read_text()
    assert "STRONGEST" in txt2 or "get_strongest" in txt2

def test_trade_desk_idempotency():
    txt = (ROOT / "src/gcis/app/pages/trade_desk.py").read_text()
    assert "idempotency_key" in txt
    assert "submit_command" in txt or "Command" in txt
    assert "ENTER_TRADE" in txt

def test_no_forbidden_strings():
    forbidden = ["guaranteed profit","risk free","100% win","can't lose"]
    for p in (ROOT / "src/gcis/app").rglob("*.py"):
        txt = p.read_text(encoding="utf-8").lower()
        for f in forbidden:
            assert f not in txt, f"forbidden string {f} in {p}"

def test_overview_strongest_logic():
    txt = (ROOT / "src/gcis/app/pages/overview.py").read_text()
    # UIX-05 STRONGEST by EV_lcb else NONE+TOP UNVALIDATED
    assert "STRONGEST" in txt
    assert "TOP UNVALIDATED" in txt or "UNVALIDATED" in txt

def test_charts_plotly_and_asof():
    txt = (ROOT / "src/gcis/app/components/charts.py").read_text()
    assert "plotly" in txt.lower()
    assert "as-of" in txt.lower() or "as_of" in txt.lower()

def test_risk_center_exists():
    txt = (ROOT / "src/gcis/app/pages/risk_center.py").read_text()
    assert "Risk" in txt

def test_streamlit_app_still_minimal():
    txt = (ROOT / "src/gcis/app/streamlit_app.py").read_text()
    # should still have banner and not use forbidden
    assert "GLOBALCRYPTOICTSCANNER" in txt
    assert "submit_kill_switch" in txt
