#!/usr/bin/env python3
"""
Environment probe v3 — probes every venue/provider in failover chains (Part 0.1.2)
Records OS, Python, Postgres, Binance UM/CM, Bybit, OKX, Hyperliquid, data.binance.vision, public.bybit.com, secondary providers, PyPI, disk.
Detects geo-restriction (451/403) and never circumvents.
"""
import json, platform, sys, shutil, ssl, socket, time, http.client
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
BUILD_STATE = ROOT / "BUILD_STATE.json"

def probe_host(host, path="/api/v3/time", timeout=6):
    try:
        conn = http.client.HTTPSConnection(host, timeout=timeout)
        conn.request("GET", path, headers={"User-Agent": "GCIS-probe/3.0"})
        r = conn.getresponse()
        body = r.read()[:400].decode(errors="ignore")
        conn.close()
        if r.status == 451:
            return f"RESTRICTED_451:{r.status}"
        if r.status == 403 and "restricted" in body.lower():
            return f"RESTRICTED_403:{body[:80]}"
        if r.status < 500:
            return f"reachable:{r.status}"
        return f"http_{r.status}"
    except Exception as e:
        # TCP check
        try:
            s = socket.create_connection((host, 443), timeout=4)
            s.close()
            return f"tcp_ok_but_tls_failed:{type(e).__name__}"
        except Exception as e2:
            return f"unreachable:{type(e).__name__}:{e}"

def probe_pypi():
    return probe_host("pypi.org", "/simple/")

def probe_postgres():
    for cmd in ["psql", "pg_isready"]:
        if shutil.which(cmd):
            try:
                import subprocess
                out = subprocess.run([cmd, "--version"] if cmd=="psql" else [cmd], capture_output=True, text=True, timeout=5)
                return f"found:{cmd}:{out.stdout.strip()[:120] or out.stderr.strip()[:120]}"
            except Exception as e:
                return f"found_but_error:{e}"
    try:
        import psycopg as _  # noqa
        return "driver_available_no_server"
    except:
        try:
            import psycopg2 as _  # noqa
            return "driver_available_no_server"
        except:
            return "unknown_no_client"

# v3 venues
VENUES = {
    "binance_um": ("fapi.binance.com", "/fapi/v1/time"),
    "binance_cm": ("dapi.binance.com", "/dapi/v1/time"),
    "bybit": ("api.bybit.com", "/v5/market/time"),
    "okx": ("www.okx.com", "/api/v5/public/time"),
    "hyperliquid": ("api.hyperliquid.xyz", "/info"),
    "data_binance_vision": ("data.binance.vision", "/"),
    "public_bybit": ("public.bybit.com", "/"),
    "coinpaprika": ("api.coinpaprika.com", "/v1/global"),
    "alternative_me": ("api.alternative.me", "/fng/?limit=1"),
}

def main():
    env = {}
    env["os"] = f"{platform.system()} {platform.release()} ({platform.version()}) - {platform.platform()}"
    env["python"] = sys.version.replace("\n"," ")
    env["python_executable"] = sys.executable
    env["postgres"] = probe_postgres()
    venues = {}
    for k, (host, path) in VENUES.items():
        # Hyperliquid needs POST for /info, we probe with GET will get 405 but still reachable
        status = probe_host(host, path)
        venues[k] = status
        print(f"{k:20s} {host:30s} -> {status}")
        time.sleep(0.15)
    env["network_venues"] = venues
    # keep legacy key for compat if needed
    env["network_binance"] = venues.get("binance_um", "unknown")
    env["network_pypi"] = probe_pypi()
    env["disk_free_gb"] = round(shutil.disk_usage(str(ROOT)).free / (1024**3), 2)
    env["probed_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(env, indent=2, ensure_ascii=False))
    if BUILD_STATE.exists():
        data = json.loads(BUILD_STATE.read_text(encoding="utf-8"))
        # merge preserve other fields, update environment with v3 schema
        data["environment"] = env
        BUILD_STATE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nUpdated {BUILD_STATE}")
    else:
        print(f"No BUILD_STATE.json at {BUILD_STATE}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
