import argparse, json, sys, time
from pathlib import Path
from datetime import datetime, timezone

def cmd_preflight(args):
    print("=== GCIS Preflight ===")
    from gcis.core.config import load_config
    try:
        cfg = load_config()
        print(f"Config loaded: mode={cfg.get('app',{}).get('mode')} db={cfg.get('database',{}).get('url')}")
    except Exception as e:
        print(f"CONFIG ERROR: {e}", file=sys.stderr)
        return 1
    # Python version
    import platform
    print(f"Python {platform.python_version()} OS {platform.platform()}")
    # DB
    try:
        from gcis.persistence.db import init_db, get_session
        engine = init_db()
        print(f"DB engine {engine.url}")
        # migrations at head? we just create tables
        s = get_session()
        s.close()
        print("DB reachable: OK")
    except Exception as e:
        print(f"DB ERROR: {e}", file=sys.stderr)
        # not fatal for NO DATA mode
    # tzdata
    try:
        import zoneinfo
        zoneinfo.ZoneInfo("America/New_York")
        print("Timezone DB: OK")
    except Exception as e:
        print(f"TZ ERROR: {e}", file=sys.stderr)
        return 1
    # disk
    import shutil
    free = shutil.disk_usage(".").free / (1024**3)
    print(f"Disk free {free:.1f} GB")
    if free < 2:
        print("DISK LOW", file=sys.stderr)
    # Binance reachability
    try:
        from gcis.data.exchange.binance import BinanceAdapter
        cfg_rest = cfg.get("exchange",{}).get("binance_rest_base","https://data-api.binance.vision")
        adapter = BinanceAdapter(rest_base=cfg_rest, timeout=5)
        try:
            adapter.ping()
            print(f"Binance {cfg_rest} reachable: OK")
        except Exception as e:
            print(f"Binance {cfg_rest} unreachable: {e} -> NO DATA mode (expected in sandbox)")
        adapter.close()
    except Exception as e:
        print(f"Binance probe error: {e}")
    # universe registry (P01) — try exchangeInfo with failover, honest NO DATA if blocked
    try:
        from gcis.data.universe import sync_registry
        from gcis.persistence.db import get_session
        from gcis.persistence.models import ContractRegistry
        print("Syncing contract registry (P01)...")
        session = get_session()
        # Use fixtures fallback only if explicitly in offline sandbox? honest probe: try real, if all fail show NO DATA
        result = sync_registry(session=session, timeout=5)
        if result["status"] == "HEALTHY":
            print(f"Registry: {result['venue_used']} listed={result['listed']} analysable={result['analysable']} added={result['added']} updated={result['updated']}")
            # show sample via DB
            sample = session.query(ContractRegistry).filter(ContractRegistry.status=="TRADING").limit(3).all()
            for s in sample:
                print(f"  - {s.venue}:{s.symbol} {s.contract_family} {s.contract_type}")
        else:
            print(f"Registry: NO DATA — all venues unreachable (expected in sandbox TLS block) — {result.get('error')}")
            print("  -> Fixture-based test still proves parser CODE_VERIFIED (tests/unit/test_universe.py). Run offline fixture: sync with --use-fixtures")
        session.close()
    except Exception as e:
        print(f"Registry sync error (non-fatal): {e}")
    # time sync check
    try:
        from gcis.data.time_sync import sync_time, clock_drift_ms
        t, src = sync_time(timeout=3)
        if t:
            drift = clock_drift_ms(t)
            print(f"Time sync: {src} drift={drift}ms (warn 500/block 2000)")
            if drift is not None and abs(drift) > 2000:
                print("CLOCK_DRIFT_BLOCK — new entries would be blocked (INV-10)")
        else:
            print("Time sync: NO DATA (all venues+NTP failed — CLOCK checks will block entries safely)")
    except Exception as e:
        print(f"Time sync error: {e}")
    print("Preflight done (non-fatal NO DATA allowed)")
    return 0

def cmd_verify(args):
    print("=== GCIS Verify ===")
    mode = "quick"
    if args.full:
        mode = "full"
    elif args.post_install:
        mode = "post-install"
    start = time.time()
    results = {"mode": mode, "started_at": datetime.now(timezone.utc).isoformat(), "checks": []}
    def add(name, ok, detail=""):
        results["checks"].append({"name": name, "ok": ok, "detail": detail})
        print(f"{'[OK]' if ok else '[FAIL]'} {name}: {detail}")
        return ok
    all_ok = True
    # invariant scanner
    try:
        from pathlib import Path
        import subprocess
        res = subprocess.run([sys.executable, "scripts/check_invariants.py"], capture_output=True, text=True, timeout=30)
        ok = res.returncode == 0
        all_ok &= ok
        add("check_invariants", ok, res.stdout[:500] + res.stderr[:500])
    except Exception as e:
        all_ok=False
        add("check_invariants", False, str(e))
    # config load
    try:
        from gcis.core.config import load_config
        load_config()
        add("config_load", True, "loaded")
    except Exception as e:
        all_ok=False
        add("config_load", False, str(e))
    # DB migrations — real alembic check (Phase8, no create_all fallback)
    try:
        from gcis.persistence.db import init_db, preflight_alembic_version
        engine = init_db()
        chk = preflight_alembic_version(engine)
        ok = bool(chk.get("ok") and chk.get("current") == chk.get("head"))
        add("db_migrations", ok, f"{engine.url} version {chk.get('current')} head {chk.get('head')} ok={ok} {chk.get('error','')}".strip())
    except Exception as e:
        all_ok=False
        add("db_migrations", False, str(e))
    # unit tests quick
    if args.full or args.quick:
        try:
            import subprocess
            cmd = [sys.executable, "-m", "pytest", "-q", "--tb=line"]
            if mode=="quick":
                cmd += ["-k", "not integration"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            ok = res.returncode == 0
            all_ok &= ok
            add("pytest", ok, (res.stdout[-2000:] + res.stderr[-2000:]) if res.stdout else "no output")
        except Exception as e:
            all_ok=False
            add("pytest", False, str(e))
    # live data check for post-install
    if args.post_install:
        try:
            from gcis.data.exchange.binance import BinanceAdapter
            from gcis.core.config import get_config
            cfg = get_config()
            adapter = BinanceAdapter(rest_base=cfg.get("exchange",{}).get("binance_rest_base"))
            # try fetch one klines
            try:
                data = adapter.klines("BTCUSDT","1m", limit=1)
                add("live_candle_ingest", True, f"got {len(data)} klines")
            except Exception as e:
                add("live_candle_ingest", False, f"unreachable (NO DATA): {e}")
                # not fatal? but mark as degraded
                # do not fail overall if network unreachable per OD-07
                pass
            adapter.close()
        except Exception as e:
            add("live_candle_ingest", False, str(e))
    results["all_ok"] = all_ok
    results["duration_s"] = time.time()-start
    results["finished_at"] = datetime.now(timezone.utc).isoformat()
    out_path = Path("verify_report.json")
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    audit_dir = Path(f"docs/audit/P00")
    audit_dir.mkdir(parents=True, exist_ok=True)
    Path(audit_dir/"verify_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    # update BUILD_STATE
    try:
        bs = Path("BUILD_STATE.json")
        if bs.exists():
            data = json.loads(bs.read_text(encoding="utf-8"))
            data["last_verify"] = {"command": f"verify --{mode}", "exit_code": 0 if all_ok else 1, "timestamp": datetime.now(timezone.utc).isoformat(), "log": json.dumps(results)[:5000]}
            bs.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"BUILD_STATE update failed: {e}")
    print(f"Verify {'PASSED' if all_ok else 'FAILED'} -> {out_path}")
    return 0 if all_ok else 1

def cmd_download_history(args):
    print("=== Download History (bulk + REST) P02 ===")
    from gcis.core.config import get_config
    cfg = get_config()
    print(f"Venue {getattr(args,'venue', None) or cfg.get('universe',{}).get('venue_chain',['binance_um'])[0]} TF {args.timeframe} symbols {args.symbols} ({getattr(args,'start',None)}→{getattr(args,'end',None)})")
    print("This will attempt data.binance.vision bulk zip + REST tail. Network may be blocked -> NO DATA honest + UNVERIFIED_ENV for live wall-time.")
    try:
        from gcis.data.history.loader import download_history
        res = download_history(
            symbols=args.symbols,
            venue=getattr(args, 'venue', None),
            timeframe=args.timeframe,
            start=getattr(args, 'start', None),
            end=getattr(args, 'end', None),
            market=getattr(args, 'market', 'um'),
        )
        print(json.dumps(res, indent=2, default=str)[:8000])
        # summarize
        for sym, detail in res.get("symbols", {}).items():
            bulk = detail.get("bulk", {})
            tail = detail.get("tail", {})
            print(f"  {sym}: bulk {bulk.get('rows',0)} {bulk.get('status')} | tail {tail.get('rows',0)} {tail.get('status')}")
        # quality check: if any gap, show
        disk = res.get("disk","")
        print(f"Disk {disk}")
        if any("NO DATA" in (detail.get("bulk",{}).get("status","") or "") for detail in res.get("symbols",{}).values()):
            print("History: NO DATA for bulk in sandbox TLS block is expected — CODE_VERIFIED via tests/fixtures (offline). For live, run on reachable host.")
    except Exception as e:
        print(f"History loader error (expected if OFFLINE): {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        print("Marking UNVERIFIED_ENV for DAT-10")
    return 0

def cmd_backtest(args):
    print("=== Backtest ===")
    try:
        from gcis.backtest.engine import run_backtest
        from gcis.persistence.candle_repo import SqlAlchemyCandleRepository
        repo = SqlAlchemyCandleRepository()
        res = run_backtest(symbols=args.symbols, timeframe=args.timeframe, start=args.start, end=args.end, candle_repo=repo)
        print(json.dumps(res, indent=2, default=str))
    except Exception as e:
        print(f"Backtest error: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        return 1
    return 0

def cmd_healthcheck(args):
    from gcis.runtime.health import compute_health
    h = compute_health()
    print(json.dumps(h, indent=2, ensure_ascii=False))
    return 0 if h["verdict"] in ("HEALTHY","DEGRADED") else 1

def cmd_sync_registry(args):
    print("=== Sync Contract Registry (P01 Universe) ===")
    from gcis.data.universe import sync_registry
    from gcis.persistence.db import get_session
    from gcis.persistence.models import ContractRegistry, CoverageReport, VenueStatus
    session = get_session()
    try:
        result = sync_registry(session=session, venue_chain=args.venues if args.venues else None, timeout=args.timeout, use_fixtures_on_failure=args.use_fixtures)
        print(json.dumps(result, indent=2, default=str))
        if result["status"] == "HEALTHY":
            regs = session.query(ContractRegistry).filter(ContractRegistry.status=="TRADING").limit(5).all()
            for r in regs:
                print(f"  {r.venue}:{r.symbol} family={r.contract_family} type={r.contract_type} tick={r.tick_size}")
            cov = session.query(CoverageReport).order_by(CoverageReport.created_at.desc()).first()
            if cov:
                print(f"Coverage: listed={cov.listed} analysable={cov.analysable} venue={cov.venue}")
            vs = session.query(VenueStatus).all()
            for v in vs:
                print(f"Venue {v.venue}: {v.status} active={v.active} latency={v.latency_ms}ms err={v.error_count}")
        else:
            print("NO DATA — all venues failed (honest). Use --use-fixtures to verify CODE_VERIFIED via recorded payloads.")
    except Exception as e:
        print(f"sync_registry error: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        return 1
    finally:
        session.close()
    return 0

def cmd_census(args):
    print("=== Signal Census ===")
    try:
        from gcis.backtest.census import run_census
        from gcis.persistence.candle_repo import SqlAlchemyCandleRepository
        out = run_census(candle_repo=SqlAlchemyCandleRepository())
        print(json.dumps(out, indent=2, default=str))
    except Exception as e:
        print(f"Census error: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        return 1
    return 0

def main():
    parser = argparse.ArgumentParser(prog="gcis")
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("preflight")
    p.set_defaults(func=cmd_preflight)
    v = sub.add_parser("verify")
    v.add_argument("--quick", action="store_true")
    v.add_argument("--full", action="store_true")
    v.add_argument("--post-install", action="store_true")
    v.set_defaults(func=cmd_verify)
    d = sub.add_parser("download-history")
    d.add_argument("--symbols", nargs="+", default=None, help="symbols; default from ContractRegistry TRADING else BTCUSDT")
    d.add_argument("--timeframe", default="1m")
    d.add_argument("--venue", default=None, help="venue id (binance_um default)")
    d.add_argument("--start", default=None, help="YYYY-MM-DD start for bulk")
    d.add_argument("--end", default=None, help="YYYY-MM-DD end for bulk")
    d.add_argument("--market", default="um", choices=["um","cm"], help="futures market um/cm")
    d.set_defaults(func=cmd_download_history)
    b = sub.add_parser("backtest")
    b.add_argument("--symbols", nargs="+", default=["BTCUSDT"])
    b.add_argument("--timeframe", default="15m")
    b.add_argument("--start", default=None)
    b.add_argument("--end", default=None)
    b.set_defaults(func=cmd_backtest)
    h = sub.add_parser("healthcheck")
    h.set_defaults(func=cmd_healthcheck)
    sr = sub.add_parser("sync-registry", help="P01 universe sync: exchangeInfo -> contract_registry with failover")
    sr.add_argument("--venues", nargs="*", default=None, help="override venue_chain")
    sr.add_argument("--timeout", type=int, default=10)
    sr.add_argument("--use-fixtures", action="store_true", help="fallback to recorded fixtures if live fails (tests)")
    sr.set_defaults(func=cmd_sync_registry)
    c = sub.add_parser("census")
    c.set_defaults(func=cmd_census)
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
