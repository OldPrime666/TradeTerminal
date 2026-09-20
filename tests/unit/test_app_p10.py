"""P10 Minimal UI tests: read-only, banner, kill switch, health, .bat wrappers, verify --post-install."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
APP = ROOT / "src/gcis/app/streamlit_app.py"

def test_banner_and_health_present():
    txt = APP.read_text(encoding="utf-8")
    # UIX-04 banner: GLOBALCRYPTOICTSCANNER, Mode, Data, DB, Transport
    assert "GLOBALCRYPTOICTSCANNER" in txt
    assert "Mode:" in txt or "mode" in txt.lower()
    assert "Data:" in txt
    assert "Transport:" in txt
    # health
    assert "compute_health" in txt
    assert "verdict" in txt
    # UTC/London/NY per ANA-03
    assert "ZoneInfo" in txt and "Europe/London" in txt
    # Venue failover banner
    assert "VENUE_FALLBACK_ACTIVE" in txt or "Coverage" in txt

def test_kill_switch_via_command():
    txt = APP.read_text(encoding="utf-8")
    # UIX-01 kill switch must go via commands (idempotency) not direct session_state trading
    assert "KILL SWITCH" in txt
    # should use submit_kill_switch or Command
    assert "submit_kill_switch" in txt or "Command" in txt
    # should have idempotency_key
    assert "idempotency_key" in txt

def test_no_session_state_trading():
    txt = APP.read_text(encoding="utf-8")
    # INV-06: no session_state for trading state
    # allow session_state for UI controls but not for order/position
    assert "session_state" not in txt.lower() or "order" not in txt.lower()
    # ensure no import of execution/risk internals
    assert "from gcis.execution" not in txt
    assert "from gcis.risk.manager" not in txt

def test_no_business_loop_in_streamlit():
    txt = APP.read_text(encoding="utf-8")
    assert "while True" not in txt

def test_bat_wrappers_exist_and_thin():
    for name in ["start.bat", "verify.bat", "start.sh", "install.sh", "install.bat"]:
        p = ROOT / name
        assert p.exists(), f"{name} missing"
        txt = p.read_text(encoding="utf-8", errors="ignore")
        # thin wrapper: should call python -m gcis.cli or streamlit
        assert "python" in txt.lower() or "streamlit" in txt.lower()
        # should not contain business logic
        assert "KillSwitch" not in txt

def test_verify_post_install_unverified_env():
    # Verify harness should handle UNVERIFIED_ENV for Binance TLS blocked
    import subprocess, sys, json
    res = subprocess.run([sys.executable, "-m", "gcis.cli", "verify", "--post-install"], capture_output=True, text=True, timeout=30)
    # Should exit 0 even if live unreachable, but report check_invariants OK
    assert res.returncode == 0 or "UNVERIFIED_ENV" in res.stdout or "NO DATA" in res.stdout
    # check verify_report.json exists and has all_ok true (since live failure not fatal)
    import pathlib, json
    rep = pathlib.Path("verify_report.json")
    assert rep.exists()
    data = json.loads(rep.read_text(encoding="utf-8"))
    # At least check_invariants OK
    assert any(c["name"]=="check_invariants" and c["ok"] for c in data["checks"])

def test_streamlit_app_imports_without_streamlit_server():
    # Smoke: can import health and config without running streamlit
    from gcis.runtime.health import compute_health
    from gcis.core.config import get_config
    cfg = get_config()
    assert "app" in cfg
    # health should return verdict
    h = compute_health()
    assert "verdict" in h
    assert h["verdict"] in ("HEALTHY","DEGRADED","UNHEALTHY","UNKNOWN")

def test_readonly_tabs_exist():
    txt = APP.read_text(encoding="utf-8")
    # P10 tabs: Overview, Scanner, Coin Detail, Risk Center, System Health, Research
    for tab in ["Overview","Scanner","Coin Detail","Risk Center","System Health","Research"]:
        assert tab in txt
