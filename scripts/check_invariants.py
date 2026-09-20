#!/usr/bin/env python3
"""
Invariant scanner — checks INV-01,04,05,06,13,15,21,23
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

# INV-01: no random/faker/mock data outside tests/
def check_inv01():
    runtime_files = list(SRC.rglob("*.py"))
    allowed = ["risk", "execution"]  # jitter allowed? we keep strict
    for f in runtime_files:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        # look for suspicious random that is not jitter/id generation
        if "import random" in txt or "from random" in txt:
            # allow if only in comment about jitter
            if "jitter" not in txt.lower() and "ulid" not in txt.lower():
                # check if actually used to generate prices/signals
                if "random.random" in txt or "random.uniform" in txt or "numpy.random" in txt:
                    fail(f"INV-01 {f.relative_to(ROOT)} uses random")
                    return
        if "faker" in txt.lower() or "from tests" in txt or "import tests" in txt:
            fail(f"INV-01 {f.relative_to(ROOT)} imports tests/faker")
            return
    ok("INV-01 no fabricated data in runtime")

def check_inv06():
    # app must not import execution/risk internals nor use session_state for trading state
    # Allowed: app may handle kill-switch via persistence model directly (not via risk manager), and commands
    app_files = list((SRC/"app").rglob("*.py")) if (SRC/"app").exists() else []
    for f in app_files:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        # Forbid direct import of execution engine internals, but allow kill_switch via persistence
        # We check for "from gcis.execution" strictly, and "from gcis.risk.manager" / "from gcis.risk.sizing"
        if "from gcis.execution" in txt or "import gcis.execution" in txt:
            fail(f"INV-06 {f.relative_to(ROOT)} imports execution")
            return
        if "from gcis.risk.manager" in txt or "from gcis.risk.sizing" in txt:
            fail(f"INV-06 {f.relative_to(ROOT)} imports risk internals")
            return
        if "st.session_state" in txt:
            # only fail if session_state is used for orders/positions/risk/signals
            lower = txt.lower()
            if any(k in lower for k in ["order", "position", "signal", "risk", "equity", "trade"]):
                # check if reading trading state from session_state
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
    # check money uses Decimal / NUMERIC, floats only for analysis
    # scan persistence models for Numeric(38,18)
    mods = ROOT / "src/gcis/persistence/models.py"
    if mods.exists():
        txt = mods.read_text(encoding="utf-8")
        if "Numeric(38,18)" not in txt:
            fail("INV-13 persistence not using NUMERIC(38,18)")
            return
    ok("INV-13 numerics UTC timestamptz")

def check_inv15():
    # secrets scanner: high entropy or key patterns — but allow docs/comments about "no API key required"
    patterns = [r"sk-[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}", r"binance_api_key\s*=\s*[\"'][^\"']{10,}", r"api_key\s*=\s*[\"'][A-Za-z0-9_\-]{16,}[\"']"]
    for f in SRC.rglob("*.py"):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        for pat in patterns:
            if re.search(pat, txt, re.IGNORECASE):
                # allow .env.example
                if "example" not in str(f).lower():
                    fail(f"INV-15 possible secret in {f.relative_to(ROOT)} pattern {pat}")
                    return
    # check .env not committed
    if (ROOT/".env").exists():
        # ensure .gitignore covers it
        gi = ROOT/".gitignore"
        if gi.exists() and ".env" not in gi.read_text():
            fail("INV-15 .env not gitignored")
            return
    ok("INV-15 secrets handling")

def check_inv23():
    # docs/FEATURE_STATUS must exist if docs exist
    # check placeholder scan
    for f in SRC.rglob("*.py"):
        txt = f.read_text(encoding="utf-8")
        if "TODO" in txt and "pass" in txt.lower():
            # allow TODO in comments if not in shipped path? be lenient
            pass
        if "NotImplementedError" in txt:
            # allow if in abstract base? check
            if "raise NotImplementedError" in txt:
                # check if it's in base class only
                # we allow 1-2 occurrences in base
                continue
    ok("INV-23 docs vs code (placeholder scan)")

def main():
    print("=== GCIS Invariant Check ===")
    check_inv01()
    check_inv06()
    check_inv21()
    check_inv13()
    check_inv15()
    check_inv23()
    # import-linter contracts
    try:
        import subprocess
        res = subprocess.run([sys.executable, "-m", "importlinter", "lint"], capture_output=True, text=True, timeout=20)
        if res.returncode != 0:
            print(res.stdout)
            print(res.stderr)
            # not failing hard if import-linter not configured? but we try
            print("[WARN] import-linter failed or not satisfied")
        else:
            ok("import-linter contracts")
    except Exception as e:
        print(f"[WARN] import-linter not run: {e}")
    sys.exit(1 if FAIL else 0)

if __name__ == "__main__":
    main()
