#!/usr/bin/env python3
"""
Environment probe — records OS, Python, Postgres, Binance reachability, PyPI, disk into BUILD_STATE.json
As per 0.1 bootstrap step 2.
"""
import json, platform, sys, shutil, os, ssl, socket, time
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
BUILD_STATE = ROOT / "BUILD_STATE.json"

def probe_binance():
    """Try REST time + optional WS connect. Return status string."""
    hosts = [
        ("data-api.binance.vision", "/api/v3/time"),
        ("api.binance.com", "/api/v3/ping"),
    ]
    # Try http.client for each
    import http.client
    for host, path in hosts:
        try:
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(host, timeout=6)
            conn.request("GET", path, headers={"User-Agent": "GCIS-probe/1.0"})
            r = conn.getresponse()
            body = r.read()[:500]
            conn.close()
            if r.status < 500:
                # WS probe (optional)
                ws_status = "ws_unknown"
                try:
                    import asyncio, websockets
                    async def _ws():
                        uri = "wss://data-stream.binance.vision/ws/btcusdt@trade"
                        async with websockets.connect(uri, open_timeout=5) as ws:
                            await asyncio.wait_for(ws.recv(), timeout=5)
                            return "ws_ok"
                    # websockets may not be installed yet
                    ws_status = "ws_skipped_no_lib"
                except Exception as e:
                    ws_status = f"ws_probe:{type(e).__name__}"
                return f"reachable:{host}{path} HTTP {r.status} {ws_status}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            continue
    # Try generic TCP check
    try:
        s = socket.create_connection(("data-api.binance.vision", 443), timeout=5)
        s.close()
        return "tcp_reachable_but_tls_failed"
    except Exception as e:
        return f"unreachable:{type(e).__name__}: {e}"

def probe_pypi():
    import http.client
    try:
        conn = http.client.HTTPSConnection("pypi.org", timeout=6)
        conn.request("GET", "/simple/")
        r = conn.getresponse()
        conn.close()
        return "reachable" if r.status == 200 else f"http_{r.status}"
    except Exception as e:
        return f"unreachable:{e}"

def probe_postgres():
    for cmd in ["psql", "pg_isready"]:
        if shutil.which(cmd):
            try:
                import subprocess
                out = subprocess.run([cmd, "--version"] if cmd=="psql" else [cmd], capture_output=True, text=True, timeout=5)
                return f"found:{cmd}:{out.stdout.strip()[:200] or out.stderr.strip()[:200]}"
            except Exception as e:
                return f"found_but_error:{e}"
    # Try import psycopg
    try:
        import psycopg as _  # noqa
        return "driver_available_no_server"
    except:
        try:
            import psycopg2 as _  # noqa
            return "driver_available_no_server"
        except:
            return "unknown_no_client"

def main():
    env = {}
    env["os"] = f"{platform.system()} {platform.release()} ({platform.version()}) - {platform.platform()}"
    env["python"] = sys.version.replace("\n"," ")
    env["python_executable"] = sys.executable
    env["postgres"] = probe_postgres()
    env["network_binance"] = probe_binance()
    env["network_pypi"] = probe_pypi()
    env["disk_free_gb"] = round(shutil.disk_usage(str(ROOT)).free / (1024**3), 2)
    env["probed_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(env, indent=2, ensure_ascii=False))
    # Update BUILD_STATE.json
    if BUILD_STATE.exists():
        try:
            data = json.loads(BUILD_STATE.read_text(encoding="utf-8"))
            data["environment"] = env
            BUILD_STATE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"\nUpdated {BUILD_STATE}")
        except Exception as e:
            print(f"Failed to update BUILD_STATE.json: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"No BUILD_STATE.json at {BUILD_STATE}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
