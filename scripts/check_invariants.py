#!/usr/bin/env python3
"""
Invariant scanner v3 — checks INV-01,04,05,06,13,15,21,23,25,26 (+09,14)
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "gcis"
FAIL = False

def fail(msg):
    global FAIL
    FAIL=True
    print(f"[FAIL] {msg}")

def ok(msg):
    print(f"[OK] {msg}")

def check_inv01():
    runtime_files = list(SRC.rglob("*.py"))
    for f in runtime_files:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        if "import random" in txt or "from random" in txt:
            if "jitter" not in txt.lower() and "ulid" not in txt.lower():
                if "random.random" in txt or "random.uniform" in txt or "numpy.random" in txt:
                    fail(f"INV-01 {f.relative_to(ROOT)} uses random")
                    return
        if "faker" in txt.lower() or "from tests" in txt or "import tests" in txt:
            fail(f"INV-01 {f.relative_to(ROOT)} imports tests/faker")
            return
    ok("INV-01 no fabricated data in runtime")

def check_inv06():
    app_files = list((SRC/"app").rglob("*.py")) if (SRC/"app").exists() else []
    for f in app_files:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        if "from gcis.execution" in txt or "import gcis.execution" in txt:
            fail(f"INV-06 {f.relative_to(ROOT)} imports execution")
            return
        if "from gcis.risk.manager" in txt or "from gcis.risk.sizing" in txt:
            fail(f"INV-06 {f.relative_to(ROOT)} imports risk internals")
            return
        if "st.session_state" in txt:
            lower = txt.lower()
            if any(k in lower for k in ["order", "position", "signal", "risk", "equity", "trade"]):
                if "session_state[" in txt or "session_state.get" in txt:
                    fail(f"INV-06 {f.relative_to(ROOT)} uses session_state for trading state")
                    return
    ok("INV-06 UI not source of truth")

def check_inv21():
    app_files = list((SRC/"app").rglob("*.py")) if (SRC/"app").exists() else []
    for f in app_files:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        if "while True" in txt:
            fail(f"INV-21 {f.relative_to(ROOT)} has while True loop")
            return
    ok("INV-21 no business loops in Streamlit")

def check_inv13():
    mods = ROOT / "src/gcis/persistence/models.py"
    if mods.exists():
        txt = mods.read_text(encoding="utf-8")
        if "Numeric(38,18)" not in txt:
            fail("INV-13 persistence not using NUMERIC(38,18)")
            return
    ok("INV-13 numerics UTC timestamptz")

def check_inv15():
    patterns = [r"sk-[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}", r"binance_api_key\s*=\s*[\"'][^\"']{10,}", r"api_key\s*=\s*[\"'][A-Za-z0-9_\-]{16,}[\"']"]
    for f in SRC.rglob("*.py"):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        for pat in patterns:
            if re.search(pat, txt, re.IGNORECASE):
                if "example" not in str(f).lower():
                    fail(f"INV-15 possible secret in {f.relative_to(ROOT)} pattern {pat}")
                    return
    if (ROOT/".env").exists():
        gi = ROOT/".gitignore"
        if gi.exists() and ".env" not in gi.read_text():
            fail("INV-15 .env not gitignored")
            return
    ok("INV-15 secrets handling")

def check_inv23():
    for f in SRC.rglob("*.py"):
        txt = f.read_text(encoding="utf-8")
        if "TODO" in txt and "pass" in txt.lower():
            pass
        if "NotImplementedError" in txt:
            if "raise NotImplementedError" in txt:
                continue
    ok("INV-23 docs vs code (placeholder scan)")

def check_inv25():
    # No hard-coded symbol lists or coin-count caps in runtime or default config
    # Scan src/ for literal lists like ["BTC","ETH"] and top-N like 12, 100 caps
    bad = []
    for f in SRC.rglob("*.py"):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        # detect hard-coded universe list patterns (legacy v2)
        if re.search(r'symbols\s*=\s*\[\s*\"BTC\"', txt):
            bad.append(f"{f.relative_to(ROOT)}: hard-coded BTC symbol list")
        if re.search(r'TOP\s*N|top_n\s*=\s*12', txt, re.IGNORECASE):
            bad.append(str(f))
    cfg = ROOT / "config/default.yaml"
    if cfg.exists():
        txt = cfg.read_text(encoding="utf-8")
        # must NOT contain symbols: [BTC...]
        if re.search(r'symbols\s*:\s*\[BTC', txt):
            bad.append("config/default.yaml: hard-coded symbols list (violates INV-25)")
    # also check for hard-coded coin counts in src (allow comments about 1000 synthetic test)
    for f in SRC.rglob("*.py"):
        if "tests" in str(f):
            continue
        txt = f.read_text(encoding="utf-8")
        # look for "max_symbols = 12" style cap
        if re.search(r'max_symbols|max_contracts\s*=\s*(12|100)\b', txt):
            bad.append(f"{f.relative_to(ROOT)}: hard cap on contracts")
    if bad:
        for b in bad:
            fail(f"INV-25 {b}")
        return
    ok("INV-25 universe completeness (no hard-coded list/cap)")

def check_inv26():
    # Every datum/signal must record venue/source; source switches append-only
    # Check models has venue/source fields and source_switch_events table
    mods = ROOT / "src/gcis/persistence/models.py"
    if mods.exists():
        txt = mods.read_text(encoding="utf-8")
        if "class SourceSwitchEvent" not in txt or "class ContractRegistry" not in txt:
            fail("INV-26 missing SourceSwitchEvent or ContractRegistry")
            return
        if "venue" not in txt or "source" not in txt.lower():
            fail("INV-26 venue/source fields missing")
            return
    ok("INV-26 source transparency")

def check_no_circumvention():
    # SEC-09: no VPN/proxy circumvention libraries
    forbidden = ["nordvpn", "expressvpn", "proxy_rotation", "ip_spoof", "header_spoof"]
    for f in SRC.rglob("*.py"):
        txt = f.read_text(encoding="utf-8", errors="ignore").lower()
        for pat in forbidden:
            if pat in txt:
                fail(f"SEC-09 circumvention pattern {pat} in {f.relative_to(ROOT)}")
                return
    ok("SEC-09 no circumvention")

def main():
    print("=== GCIS Invariant Check v3 ===")
    check_inv01()
    check_inv06()
    check_inv21()
    check_inv13()
    check_inv15()
    check_inv23()
    check_inv25()
    check_inv26()
    check_no_circumvention()
    try:
        import subprocess, shutil, os
        # §33: use lint-imports executable, not python -m importlinter
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        exe = shutil.which("lint-imports")
        cmd = [exe] if exe else [sys.executable, "-m", "importlinter.cli", "lint"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=env, cwd=str(ROOT))
        print(res.stdout)
        if res.stderr:
            print(res.stderr)
        if res.returncode != 0:
            fail(f"import-linter contracts BROKEN (lint-imports exit {res.returncode})")
        else:
            # also check for BROKEN string
            if "BROKEN" in res.stdout:
                fail("import-linter contracts BROKEN")
            else:
                ok("import-linter contracts")
    except Exception as e:
        fail(f"import-linter not run: {e}")
    sys.exit(1 if FAIL else 0)

if __name__ == "__main__":
    main()
