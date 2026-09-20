"""
BKT-07 Walk-forward with purge & embargo (purged CV).
Deterministic, causal, no lookahead.
Config: backtest.walk_forward {train_days, test_days, purge_bars, embargo_bars}
"""
import pandas as pd
from datetime import timezone
from typing import List, Dict, Any
import hashlib
import json
from gcis.backtest.metrics import compute_metrics
from gcis.backtest.fidelity import resolve_exit_pessimistic
from gcis.core.config import get_config
from gcis.market.view import MarketView

TF_MIN = {"1m":1,"5m":5,"15m":15,"1h":60,"4h":240,"1d":1440}

def _bars_for_days(days: int, tf: str) -> int:
    m = TF_MIN.get(tf, 15)
    return int(days * 1440 // m)

def walk_forward_splits(df: pd.DataFrame, timeframe: str, train_days: int, test_days: int, purge_bars: int, embargo_bars: int):
    """
    Generate purged folds: train | purge | test | embargo
    df must be sorted by open_time.
    Returns list of dicts {fold, train_start, train_end, test_start, test_end}
    Indices inclusive/exclusive as python slices.
    """
    train_bars = _bars_for_days(train_days, timeframe)
    test_bars = _bars_for_days(test_days, timeframe)
    n = len(df)
    folds = []
    start = 0
    fold = 0
    while True:
        train_end = start + train_bars
        test_start = train_end + purge_bars
        test_end = test_start + test_bars
        embargo_end = test_end + embargo_bars
        if test_end > n:
            break
        # embargo ensures next train starts after
        folds.append({
            "fold": fold,
            "train_start": start,
            "train_end": train_end,
            "purge": (train_end, test_start),
            "test_start": test_start,
            "test_end": test_end,
            "embargo": (test_end, min(embargo_end, n)),
            "train_bars": train_bars,
            "test_bars": test_bars,
        })
        fold += 1
        # next start after embargo
        start = min(embargo_end, n)
        if start + train_bars + purge_bars + test_bars > n:
            break
        if fold > 100:  # safety
            break
    return folds

def run_walk_forward(symbols: List[str], timeframe: str = "15m", df_override: pd.DataFrame | None = None,
                     train_days: int | None = None, test_days: int | None = None,
                     purge_bars: int | None = None, embargo_bars: int | None = None,
                     strategy_name: str = "ICT-A") -> Dict[str, Any]:
    cfg = get_config()
    wf_cfg = cfg.get("backtest",{}).get("walk_forward", {})
    train_days = train_days if train_days is not None else wf_cfg.get("train_days", 180)
    test_days = test_days if test_days is not None else wf_cfg.get("test_days", 30)
    purge_bars = purge_bars if purge_bars is not None else wf_cfg.get("purge_bars", 24)
    embargo_bars = embargo_bars if embargo_bars is not None else wf_cfg.get("embargo_bars", 12)

    # Resolve df
    if df_override is not None:
        df = df_override.copy()
        if df.empty:
            return {"status":"NO_DATA","folds":[],"metrics":{}, "note":"empty df"}
    else:
        from gcis.backtest.engine import _fetch_candles, _df_from_rows
        rows = _fetch_candles(symbols or ["BTCUSDT"], timeframe)
        df = _df_from_rows(rows)
        if df.empty:
            return {"status":"NO_DATA","folds":[],"metrics":{}, "note":"no candles in DB -> NO DATA honest"}

    # Ensure sorted
    if "open_time" in df.columns:
        df = df.sort_values("open_time").reset_index(drop=True)
    folds_meta = walk_forward_splits(df, timeframe, train_days, test_days, purge_bars, embargo_bars)
    if not folds_meta:
        return {"status":"INSUFFICIENT_HISTORY","folds":[],"metrics":{"status":"INSUFFICIENT_HISTORY"}, "train_days":train_days,"test_days":test_days, "note": f"need {train_days+test_days} days but have {len(df)} bars"}

    # resolve strategy func
    def _strategy_fn(name):
        if name == "EMA-CROSS":
            from gcis.strategies.extra import evaluate_ema_cross
            return evaluate_ema_cross
        if name == "DONCHIAN":
            from gcis.strategies.extra import evaluate_donchian
            return evaluate_donchian
        if name == "RSI-REV":
            from gcis.strategies.extra import evaluate_rsi_reversion
            return evaluate_rsi_reversion
        if name == "CONFLUENCE":
            from gcis.strategies.extra import evaluate_confluence
            return evaluate_confluence
        from gcis.strategies.ict_a import evaluate_ict_a
        return evaluate_ict_a

    strat_fn = _strategy_fn(strategy_name)
    symbol = symbols[0] if symbols else "SYNTH"
    # For each fold, evaluate on test window using shared core loop
    fold_results = []
    all_out_test_trades = []
    for f in folds_meta:
        test_df = df.iloc[f["test_start"]:f["test_end"]].copy()
        # Need full history up to test_start-1 for view context (train + purge)
        # We'll loop over test window bars incrementally with MarketView using prefix up to i
        trades = []
        # offset base index
        for rel_i in range(50, len(test_df)-1):  # need warmup within test but view needs global prefix
            global_i = f["test_start"] + rel_i
            if global_i >= len(df)-1:
                break
            sub = df.iloc[:global_i+1].copy()  # causal prefix up to global_i
            # need at least 50 bars in sub (global prefix)
            if len(sub) < 50:
                continue
            as_of = sub.iloc[-1]["close_time"]
            # ensure tz aware
            if isinstance(as_of, pd.Timestamp) and as_of.tz is None:
                as_of = as_of.tz_localize("UTC")
            elif hasattr(as_of, "tzinfo") and as_of.tzinfo is None:
                as_of = as_of.replace(tzinfo=timezone.utc)
            # MarketView
            try:
                view = MarketView(as_of=as_of, candles={symbol: {timeframe: sub}}, quotes={symbol: {"updated_at": as_of, "price": float(sub.iloc[-1]["close"])}})
            except Exception:
                continue
            try:
                res = strat_fn(view, symbol, cfg)
            except Exception:
                continue
            if not res.eligible:
                continue
            # create trade similar to engine
            try:
                if getattr(res, "entry_zone", None) and len(res.entry_zone)==2:
                    entry = float((res.entry_zone[0] + res.entry_zone[1]) / 2)  # Decimal
                else:
                    entry = float(sub.iloc[-1]["close"])
            except:
                entry = float(sub.iloc[-1]["close"])
            try:
                stop = float(res.invalidation) if getattr(res, "invalidation", None) is not None else (entry*0.995 if res.direction=="LONG" else entry*1.005)
            except:
                stop = entry*0.995 if res.direction=="LONG" else entry*1.005
            targets = getattr(res, "targets", None)
            if isinstance(targets,(list,tuple)) and targets and targets[0] is not None:
                try: target = float(targets[0])
                except: target = None
            else:
                target = None
            if target is None:
                dist = abs(entry-stop)
                target = entry+dist*2 if res.direction=="LONG" else entry-dist*2
            direction = getattr(res,"direction","LONG")
            # resolve exit within test window only (pessimistic)
            exit_price=None; exit_reason=None; exit_idx=None
            search_end = min(global_i+50, f["test_end"]-1, len(df)-1)
            for j in range(global_i+1, search_end+1):
                bh = float(df.iloc[j]["high"]); bl = float(df.iloc[j]["low"])
                hit = resolve_exit_pessimistic(bh, bl, stop, target, direction, policy="stop_first")
                if hit=="STOP":
                    exit_price=stop; exit_reason="STOP"; exit_idx=j; break
                if hit=="TARGET":
                    exit_price=target; exit_reason="TARGET"; exit_idx=j; break
            if exit_price is None:
                # if not hit within test window, time exit at end of test window
                j = f["test_end"]-1
                exit_price = float(df.iloc[j]["close"]); exit_reason="TIME_EXIT"; exit_idx=j
            cost = entry*0.0005 + exit_price*0.0005
            if direction=="LONG":
                pnl = (exit_price - entry) - cost
            else:
                pnl = (entry - exit_price) - cost
            risk = abs(entry-stop) if stop else entry*0.005
            ret_r = pnl/risk if risk else 0
            trades.append({"entry":entry,"exit":exit_price,"direction":direction,"pnl":pnl,"net_pnl":pnl,"return_r":ret_r,"exit_reason":exit_reason, "fold": f["fold"]})
        metrics = compute_metrics(trades, bars=len(test_df), timeframe=timeframe)
        fold_results.append({"fold": f["fold"], "train": (f["train_start"], f["train_end"]), "test": (f["test_start"], f["test_end"]), "purge": f["purge"], "embargo": f["embargo"], "trades_count": len(trades), "metrics": metrics, "trades_sample": trades[:3]})
        all_out_test_trades.extend(trades)

    # overall out-of-sample metrics (pooled OOS)
    overall_metrics = compute_metrics(all_out_test_trades, bars=sum(f["test_bars"] for f in folds_meta), timeframe=timeframe)
    # diagnosis: leakage check — ensure purge/embargo respected (indexes don't overlap)
    leakage = False
    for i in range(len(folds_meta)-1):
        if folds_meta[i]["test_end"] > folds_meta[i+1]["train_start"]:
            leakage=True
    return {
        "status": "OK" if folds_meta else "INSUFFICIENT_HISTORY",
        "timeframe": timeframe,
        "train_days": train_days,
        "test_days": test_days,
        "purge_bars": purge_bars,
        "embargo_bars": embargo_bars,
        "folds_count": len(folds_meta),
        "folds": folds_meta,
        "fold_results": fold_results,
        "oos_metrics": overall_metrics,
        "oos_trades_count": len(all_out_test_trades),
        "leakage_check": not leakage,
        "lineage": {"config_version": getattr(__import__('gcis.backtest.engine', fromlist=['_config_version']), '_config_version')(), "strategy": strategy_name},
        "note": "Purged CV: train | purge | test | embargo; OOS pooled; leakage_check ensures test_end <= next train_start."
    }
