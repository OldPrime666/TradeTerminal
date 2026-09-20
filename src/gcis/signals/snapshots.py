"""
SIG-06 Snapshots + explainability
Captures view slice, ICT context, strategy evidence, fusion result, gates, and
produces evidence_hash for replay. Causal: snapshot taken at signal creation time
using only closed data as_of created_at.
"""
import hashlib, json
from datetime import datetime, timezone
from typing import Dict
import pandas as pd

def capture_snapshot(view, symbol: str, timeframe: str, strategy_result, fusion_result, mv_gates, px_gates, config: dict) -> Dict:
    """
    Returns dict snapshot with deterministic evidence_hash.
    Includes: symbol, timeframe, created_at, view quality, strategy evidence, fusion, gates, config_version.
    """
    created = datetime.now(timezone.utc)
    # Try to get closed candles slice for explainability
    try:
        df = view.get_closed_candles(symbol, timeframe) if view else pd.DataFrame()
        candles_tail = df.tail(5).to_dict(orient="records") if not df.empty else []
        # Convert Decimals to strings for JSON
        for rec in candles_tail:
            for k,v in list(rec.items()):
                if hasattr(v, "quantize"):
                    rec[k]=str(v)
                elif isinstance(v, (datetime)):
                    rec[k]=v.isoformat()
    except:
        candles_tail = []
    evidence = getattr(strategy_result, "evidence", []) or []
    payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "captured_at": created.isoformat(),
        "view_quality": view.quality_state(symbol) if view and hasattr(view, "quality_state") else "UNKNOWN",
        "strategy": getattr(strategy_result, "strategy_name", "ICT-A"),
        "strategy_version": getattr(strategy_result, "strategy_version", "0.1.0"),
        "direction": getattr(strategy_result, "direction", None),
        "setup_score": getattr(strategy_result, "setup_score", 0),
        "fusion_score": getattr(fusion_result, "setup_score", 0) if fusion_result else 0,
        "fusion_grade": getattr(fusion_result, "grade", "D") if fusion_result else "D",
        "evidence": evidence,
        "mv_gates": mv_gates or [],
        "px_gates": px_gates or [],
        "candles_tail": candles_tail,
        "config_version": config.get("version", "0.1.0") if config else "0.1.0",
    }
    # deterministic hash over evidence + gates + direction
    hash_input = json.dumps({"evidence": evidence, "mv": mv_gates, "px": px_gates, "dir": getattr(strategy_result, "direction", None)}, sort_keys=True).encode()
    evidence_hash = hashlib.sha256(hash_input).hexdigest()[:16]
    payload["evidence_hash"] = evidence_hash
    # also include in snapshot for DB
    return payload

def snapshot_to_signal_fields(snapshot: Dict) -> Dict:
    """
    Maps snapshot to Signal DB columns for persistence.
    """
    return {
        "evidence_hash": snapshot.get("evidence_hash"),
        "analysis_version": snapshot.get("strategy_version"),
        "config_version": snapshot.get("config_version"),
        "setup_score": snapshot.get("fusion_score"),
        "setup_quality": snapshot.get("fusion_grade"),
    }
