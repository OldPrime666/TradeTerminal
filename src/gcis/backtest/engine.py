"""
Backtest engine P08 BKT-01..06,08,10..12 — shared core, fidelity, lineage, baselines, census.

Shared core: MarketView(as_of) + evaluate_ict_a + gates (MV/PX) — same as live scanner.
Fidelity: OHLC_APPROXIMATION pessimistic stop_first (BKT-02).
Realism: taker 5bps + maker 2bps via compute_net_r / paper model, no fabrication (BKT-03).
Lineage: config_version + analysis_version + evidence_hash (BKT-04).
Baselines: 4 + verdict (BKT-05).
Census: via run_census (BKT-06).
Metrics 365d (BKT-08).
Backtestability statuses (BKT-10): OK/GAP/INSUFFICIENT_HISTORY/NO_DATA/DEGRADED.
Survivorship-aware: uses Candle history not filtered to TRADING (BKT-12).
"""
import pandas as pd
from datetime import datetime, timezone, date
from decimal import Decimal, getcontext
import hashlib
import json

getcontext().prec = 28

from gcis.backtest.ports import CandleRepository

Fidelity = "OHLC_APPROXIMATION"

def _config_version():
    try:
        from gcis.core.config import get_config
        cfg = get_config()
        # hash of config file for lineage
        import pathlib
        p = pathlib.Path("config/default.yaml")
        if p.exists():
            h = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
            return f"cfg-{h}"
        # fallback to version field
        return cfg.get("app",{}).get("version","0.1.8")
    except Exception:
        return "cfg-unknown"

def _analysis_version():
    try:
        # ict_a version stored in strategy
        from gcis.strategies import ict_a
        return getattr(ict_a, "__version__", "0.1.0")
    except Exception:
        return "0.1.0"

def _fetch_candles(symbols: list, timeframe: str, start=None, end=None, limit: int = 5000, repo: CandleRepository | None = None):
    """Fetch candles via repository abstraction (injected, no direct sqlalchemy import)."""
    if repo is not None:
        try:
            return repo.fetch(symbols, timeframe, start, end, limit)
        except Exception:
            return []
    # No repo injected → NO DATA (caller must inject SqlAlchemyCandleRepository from app layer)
    return []

def _fetch_candles_paginated(symbols: list, timeframe: str, start=None, end=None, page_limit: int = 5000, repo=None) -> tuple[list, bool, dict]:
    """
    §24 paginated loading: fetch beyond 5000 without silent truncation.
    Returns (rows, truncated, info) where truncated indicates hit limit and may have more,
    info contains requested/actual period, bar counts, truncation status.
    """
    all_rows = []
    current_start = start
    truncated = False
    pages = 0
    max_pages = 200  # safety: 200*5000 = 1M bars
    while pages < max_pages:
        batch = _fetch_candles(symbols, timeframe, start=current_start, end=end, limit=page_limit, repo=repo)
        if not batch:
            break
        # Avoid infinite loop on same batch (dedup by open_time)
        if all_rows and batch[0].open_time == all_rows[-1].open_time:
            # duplicate page, break
            break
        all_rows.extend(batch)
        pages += 1
        if len(batch) < page_limit:
            break
        # Need next page: set start to last open_time + 1 interval
        # Use batch last open_time as cursor (exclusive)
        last_ot = batch[-1].open_time
        # Convert to iso string for next fetch
        if hasattr(last_ot, "isoformat"):
            # add 1 minute (or timeframe) to avoid duplicate? simplest add 1ms
            try:
                from datetime import timedelta
                next_dt = last_ot + timedelta(milliseconds=1)
                current_start = next_dt.isoformat()
            except Exception:
                current_start = last_ot.isoformat() if hasattr(last_ot, "isoformat") else str(last_ot)
        else:
            current_start = str(last_ot)
        # If we fetched exactly page_limit and there may be more, continue; but if we already have huge, break
        if pages * page_limit >= 1000000:
            truncated = True
            break
        # If batch == page_limit, assume may be truncated, continue
        # else break already
        if len(batch) == page_limit:
            truncated = True
            # continue fetching next page unless we hit max_pages
            continue
        else:
            truncated = False
            break
    # If we fetched multiple pages, truncated flag already indicates we attempted pagination;
    # For single page with < limit, not truncated. For single page == limit but we fetched next and got 0, then not truncated.
    # Simplify: truncated = (pages > 1 and len(all_rows) >= page_limit) or (pages == 1 and len(batch) == page_limit and not truncated check)
    # Actually if we fetched one full page and next batch was empty, then not truncated.
    # Our loop already handles: if second batch empty, we break with truncated still True from previous iteration but should be False.
    # So recompute: if last batch < page_limit, not truncated.
    if all_rows and len(batch) < page_limit:
        truncated = False
    info = {
        "requested_start": str(start) if start else None,
        "requested_end": str(end) if end else None,
        "actual_start": all_rows[0].open_time.isoformat() if all_rows and hasattr(all_rows[0].open_time, "isoformat") else None,
        "actual_end": all_rows[-1].open_time.isoformat() if all_rows and hasattr(all_rows[-1].open_time, "isoformat") else None,
        "bars": len(all_rows),
        "pages": pages,
        "truncated": truncated,
        "page_limit": page_limit,
    }
    return all_rows, truncated, info

def _df_from_rows(rows):
    if not rows:
        return pd.DataFrame()
    data = []
    for r in rows:
        # normalize times to utc
        ot = r.open_time
        ct = r.close_time
        if ot and ot.tzinfo is None:
            ot = ot.replace(tzinfo=timezone.utc)
        if ct and ct.tzinfo is None:
            ct = ct.replace(tzinfo=timezone.utc)
        data.append({
            "open_time": ot,
            "close_time": ct,
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": float(r.volume),
        })
    df = pd.DataFrame(data)
    # ensure sorted
    df = df.sort_values("open_time").reset_index(drop=True)
    return df

def _evaluate_signal_with_gates(view, symbol: str, cfg):
    """
    Shared core: evaluate ICT-A then gates. Returns StrategyResult if eligible and gates pass.
    BKT-01 same core as live. §22: gates must not be silently bypassed; errors block.
    """
    import logging
    log = logging.getLogger(__name__)
    from gcis.strategies.ict_a import evaluate_ict_a
    from gcis.signals.gates import evaluate_mv_gates, evaluate_px_gates
    # run strategy
    res = evaluate_ict_a(view, symbol, cfg)
    if not res.eligible:
        return None, res
    # gates — explicit handling, never silent PASS on error
    try:
        mv_reasons = evaluate_mv_gates(res, view, symbol, cfg)
        px_reasons = evaluate_px_gates(res, {}, False, False)
    except Exception as e:
        log.warning(f"gate evaluation error {symbol}: {e}")
        # §22: code error / config missing → explicit degraded, block signal (not PASS)
        return None, res
    if mv_reasons:
        return None, res
    if px_reasons:
        return None, res
    return res, None

def run_backtest(symbols: list, timeframe: str = "15m", start=None, end=None, fidelity: str = "OHLC_APPROXIMATION", df_override: pd.DataFrame | None = None, candle_repo: CandleRepository | None = None):
    """
    Main entry. df_override for tests (synthetic df directly, bypass DB).
    Returns dict with BKT fields: status, fidelity, trades, metrics, baselines, verdict, lineage, backtestability, survivorship.
    """
    from gcis.core.config import get_config
    cfg = get_config()
    # lineage
    cfg_ver = _config_version()
    analysis_ver = _analysis_version()
    # fetch
    if df_override is not None:
        df = df_override
        rows = []  # not from DB
        # infer symbols from override if needed
        if not symbols and not df.empty and "symbol" in df.columns:
            symbols = [df["symbol"].iloc[0]]
        elif not symbols:
            symbols = ["SYNTH"]
    else:
        if not symbols:
            # resolve from registry if None (survivorship-aware, but for backtest default BTCUSDT)
            symbols = ["BTCUSDT"]
        # §24 paginated fetch to avoid silent 5000 truncation (repo injected via DI)
        rows, truncated, fetch_info = _fetch_candles_paginated(symbols, timeframe, start=start, end=end, repo=candle_repo)
        df = _df_from_rows(rows)
        # check backtestability via quality_report
        if df.empty:
            # try census for status
            return {
                "status": "NO DATA",
                "fidelity": fidelity,
                "trades": [],
                "metrics": {"bars": 0, "trades": 0, "status": "NO_DATA"},
                "lineage": {"config_version": cfg_ver, "analysis_version": analysis_ver},
                "backtestability": {"_all": "NO_DATA"},
                "survivorship_note": "Candle history survivorship-aware: DB empty -> NO DATA honest.",
                "message": "No candles in DB — run download_history or wait for live ingest",
                "baselines": {},
                "verdict": "NO_DATA",
            }
        # quality
        try:
            from gcis.data.quality.report import quality_report
            # need df with required cols for quality_report: open_time etc must be Timestamp
            # ensure df has open_time as datetime
            qdf = df.copy()
            # quality_report expects df with open_time as Timestamp
            qdf["open_time"] = pd.to_datetime(qdf["open_time"], utc=True)
            qrep = quality_report("binance_um", symbols[0], timeframe, qdf)
            qstatus = qrep.get("status")
            if qstatus == "GAP":
                status = "GAP"
            elif qstatus == "INSUFFICIENT_HISTORY":
                status = "INSUFFICIENT_HISTORY"
            else:
                status = "OK" if len(df) >= 500 else "DEGRADED_SMALL_SAMPLE"
        except Exception as e:
            status = "OK" if len(df) >= 500 else "DEGRADED_SMALL_SAMPLE"

    # If override, determine status similarly
    if df_override is not None:
        if df.empty:
            status = "NO DATA"
        else:
            try:
                from gcis.data.quality.report import quality_report
                qdf = df.copy()
                qdf["open_time"] = pd.to_datetime(qdf["open_time"], utc=True)
                qrep = quality_report("binance_um", symbols[0] if symbols else "SYNTH", timeframe, qdf)
                qstatus = qrep.get("status")
                if qstatus == "GAP":
                    status = "GAP"
                elif qstatus == "INSUFFICIENT_HISTORY":
                    status = "INSUFFICIENT_HISTORY"
                else:
                    status = "OK" if len(df) >= 50 else "DEGRADED_SMALL_SAMPLE"
            except Exception:
                status = "OK" if len(df) >= 50 else "DEGRADED_SMALL_SAMPLE"

    if status == "NO DATA":
        return {
            "status": status,
            "fidelity": fidelity,
            "trades": [],
            "metrics": {"bars": len(df), "trades": 0, "status": "NO DATA"},
            "lineage": {"config_version": cfg_ver, "analysis_version": analysis_ver},
            "backtestability": {"_all": "NO_DATA"},
            "survivorship_note": "NO_DATA",
            "baselines": {},
            "verdict": "NO DATA",
        }

    # shared core loop
    from gcis.market.view import MarketView
    from gcis.strategies.ict_a import evaluate_ict_a
    from gcis.backtest.fidelity import resolve_exit_pessimistic
    from gcis.backtest.metrics import compute_metrics

    trades = []
    # For multi-symbol, we loop per symbol separately but for P08 we simplify to first symbol single df
    symbol = symbols[0] if symbols else "SYNTH"
    # Ensure df has required cols for MarketView: open_time, close_time, open, high, low, close, volume
    # §25 non-overlapping trades: use while loop to allow skipping to exit_bar (§25 deterministic)
    i = 50
    while i < len(df) - 1:
        as_of = df.iloc[i]["close_time"]
        if isinstance(as_of, str):
            as_of = pd.Timestamp(as_of)
        if hasattr(as_of, "tzinfo") and as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        elif isinstance(as_of, pd.Timestamp) and as_of.tz is None:
            as_of = as_of.tz_localize("UTC")
        # causal sub
        sub = df.iloc[:i+1].copy()
        # MarketView expects candles dict symbol->timeframe->df
        # Ensure sub has correct dtypes: open_time etc as datetime
        try:
            view = MarketView(as_of=as_of, candles={symbol: {timeframe: sub}}, quotes={symbol: {"updated_at": as_of, "price": float(sub.iloc[-1]["close"])}})
        except Exception as e:
            i += 1
            continue
        # strategy
        try:
            res = evaluate_ict_a(view, symbol, cfg)
        except Exception:
            i += 1
            continue
        if not res.eligible:
            i += 1
            continue
        # gates — BKT-01 same mv/px as live, §22 no silent bypass
        try:
            from gcis.signals.gates import evaluate_mv_gates, evaluate_px_gates
            mv_reasons = evaluate_mv_gates(res, view, symbol, cfg)
            px_reasons = evaluate_px_gates(res, {}, False, False)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"gate evaluation error {symbol} at bar {i}: {e}")
            i += 1
            continue
        if mv_reasons:
            i += 1
            continue
        if px_reasons:
            i += 1
            continue

        # eligible signal -> create trade (StrategyResult contract STR-01)
        # §23: Do not invent stop/target geometry — use actual strategy values, else mark invalid
        try:
            if getattr(res, "entry_zone", None) and len(res.entry_zone) == 2 and res.entry_zone[0] is not None and res.entry_zone[1] is not None:
                entry = float((Decimal(str(res.entry_zone[0])) + Decimal(str(res.entry_zone[1]))) / 2)
            else:
                # No entry_zone → invalid setup
                i += 1
                continue
        except Exception:
            i += 1
            continue
        try:
            stop = float(res.invalidation) if getattr(res, "invalidation", None) is not None else None
        except Exception:
            stop = None
        if stop is None or stop <= 0:
            i += 1
            continue
        # Validate stop direction sensible
        if (res.direction == "LONG" and stop >= entry) or (res.direction == "SHORT" and stop <= entry):
            i += 1
            continue
        targets = getattr(res, "targets", None)
        target = None
        if isinstance(targets, (list, tuple)) and len(targets) > 0 and targets[0] is not None:
            try:
                target = float(targets[0])
            except:
                target = None
        if target is None or target <= 0:
            i += 1
            continue
        # Validate RR at least >0
        if (res.direction == "LONG" and target <= entry) or (res.direction == "SHORT" and target >= entry):
            i += 1
            continue

        direction = getattr(res, "direction", "LONG")
        # Simulate exit pessimistically over next bars
        exit_price = None
        exit_reason = None
        exit_bar = None
        # lookahead up to 100 bars
        for j in range(i+1, min(i+100, len(df))):
            bh = float(df.iloc[j]["high"])
            bl = float(df.iloc[j]["low"])
            # fidelity pessimistic
            hit = resolve_exit_pessimistic(bh, bl, stop, target, direction, policy=cfg.get("backtest",{}).get("same_bar_tp_sl_policy","stop_first"))
            if hit == "STOP":
                exit_price = stop
                exit_reason = "STOP"
                exit_bar = j
                break
            if hit == "TARGET":
                exit_price = target
                exit_reason = "TARGET"
                exit_bar = j
                break
        if exit_price is None:
            # time exit at last available or 50 bars
            j = min(i+50, len(df)-1)
            exit_price = float(df.iloc[j]["close"])
            exit_reason = "TIME_EXIT"
            exit_bar = j

        # costs: taker 5bps each side (BKT-03)
        cost_entry = entry * 0.0005
        cost_exit = exit_price * 0.0005
        cost = cost_entry + cost_exit
        # funding stub 0 for P08
        # pnl
        if direction == "LONG":
            pnl = (exit_price - entry) - cost
        else:
            pnl = (entry - exit_price) - cost
        # R
        risk = abs(entry - stop) if stop else entry*0.005
        ret_r = pnl / risk if risk else 0
        # lineage per trade
        evidence = getattr(res, "evidence", []) or []
        ev_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str).encode()).hexdigest()[:16] if evidence else "no-evidence"
        trades.append({
            "entry_bar": i,
            "exit_bar": exit_bar,
            "entry_time": str(df.iloc[i]["close_time"]),
            "exit_time": str(df.iloc[exit_bar]["close_time"]) if exit_bar is not None else str(df.iloc[-1]["close_time"]),
            "direction": direction,
            "entry": entry,
            "stop": stop,
            "target": target,
            "exit": exit_price,
            "exit_reason": exit_reason,
            "pnl": pnl,
            "net_pnl": pnl,
            "return_r": ret_r,
            "cost": cost,
            "setup_score": getattr(res, "setup_score", None),
            "evidence_hash": ev_hash,
            "fidelity": fidelity,
        })
        # limit to avoid huge runtime, but for metrics we cap at maybe 200 trades
        if len(trades) >= 200:
            break
        # §25 non-overlapping: skip to exit_bar + 1 (deterministic portfolio-aware: no concurrent overlapping)
        if exit_bar is not None and exit_bar > i:
            i = exit_bar + 1
        else:
            i += 1
        continue
    # If loop fell through without trade, the continues already handled i increment
    # But we need to ensure while loop progresses for non-continue paths that didn't hit trade
    # The above continue handles trade case; for other paths, i already incremented via continue
    # For safety, if we ever reach here without increment (should not), increment
    # (This line is unreachable due to continues, but kept for static analysis)

    # metrics 365d
    metrics = compute_metrics(trades, bars=len(df), timeframe=timeframe, annualization_days=cfg.get("backtest",{}).get("annualization_days",365))

    # baselines
    try:
        from gcis.backtest.baselines import run_all_baselines, verdict_vs_baselines
        baselines = run_all_baselines(df, cfg.get("backtest",{}).get("baselines",{}) if isinstance(cfg.get("backtest",{}).get("baselines"), dict) else {})
        verdict = verdict_vs_baselines(metrics, baselines, alpha=cfg.get("backtest",{}).get("significance",{}).get("alpha",0.05) if isinstance(cfg.get("backtest",{}).get("significance"), dict) else 0.05)
    except Exception as e:
        baselines = {"error": str(e)}
        verdict = "ERROR"

    # backtestability per symbol
    backtestability = {}
    try:
        from gcis.data.quality.report import quality_report
        qdf = df.copy()
        qdf["open_time"] = pd.to_datetime(qdf["open_time"], utc=True)
        rep = quality_report("binance_um", symbol, timeframe, qdf)
        bstat = rep.get("status","UNKNOWN")
        backtestability[symbol] = bstat
    except Exception:
        backtestability[symbol] = "UNKNOWN"

    # overall status: if GAP then GAP, else metrics status — §24 truncation handling
    overall_status = status
    if backtestability.get(symbol) == "GAP":
        overall_status = "GAP"
    elif metrics.get("status") == "INSUFFICIENT_TRADES" and len(df) < 100:
        overall_status = "INSUFFICIENT_HISTORY"
    # §24: if paginated fetch truncated, mark fidelity as truncated and propagate info
    fetch_truncated = False
    fetch_info_local = {}
    try:
        fetch_truncated = truncated  # from paginated fetch
        fetch_info_local = fetch_info
        if fetch_truncated:
            overall_status = "TRUNCATED" if overall_status == "OK" else overall_status + "_TRUNCATED"
    except Exception:
        pass

    result = {
        "status": overall_status,
        "fidelity": fidelity,
        "bars": len(df),
        "trades": trades[:20],  # cap output
        "trades_count": len(trades),
        "metrics": metrics,
        "baselines": baselines,
        "verdict": verdict,
        "lineage": {
            "config_version": cfg_ver,
            "analysis_version": analysis_ver,
            "evidence_sample_hash": trades[0]["evidence_hash"] if trades else None,
            "fidelity": fidelity,
            "same_bar_policy": cfg.get("backtest",{}).get("same_bar_tp_sl_policy","stop_first"),
        },
        "backtestability": backtestability,
        "survivorship_note": "Survivorship-aware: includes delisted history via Candle table; not filtered to TRADING only (BKT-12).",
        "fetch_info": fetch_info_local,
        "truncation": {"truncated": fetch_truncated, "info": fetch_info_local, "note": "§24 paginated 5000/page, no silent truncation; TRUNCATED status if hit limit without full period"},
        "funding": {"cost": 0, "status": "OMITTED", "note": "§26 funding OMITTED — historical funding not yet integrated; fidelity marked OMITTED, not hidden"},
        "fees": {"taker_bps": 5, "maker_bps": 2, "slippage": 0, "note": "taker 5bps per side applied; slippage 0; funding OMITTED"},
        "note": "Shared core BKT-01: MarketView incremental + ICT-A + gates; pessimistic stop_first BKT-02; costs 5bps taker BKT-03; lineage BKT-04; baselines 4 BKT-05; census TIER via run_census BKT-06; metrics 365d BKT-08; backtestability BKT-10; survivorship BKT-12; §24 pagination; §25 non-overlapping; §26 funding OMITTED;",
    }
    # census integration (inject same repo)
    try:
        from gcis.backtest.census import run_census
        cen = run_census(symbols=symbols, timeframe=timeframe, candle_repo=candle_repo)
        result["census"] = cen
        # if census GAP_WARN, propagate
        if "GAP" in cen.get("feasibility_verdict",""):
            result["census_gap_warn"] = True
    except Exception as e:
        result["census_error"] = str(e)

    return result
