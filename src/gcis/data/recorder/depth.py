"""
DAT-17 depth recorder — orderbook snapshots persistence.
Stores depth snapshots to var/depth/<venue>/<symbol>/YYYY-MM-DD.ndjson with 30d retention.
Deterministic, never fabricates.
"""
from pathlib import Path
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List
import logging

log = logging.getLogger(__name__)

DEPTH_ROOT = Path("var/depth")

def depth_path(venue: str, symbol: str, dt: datetime | None = None) -> Path:
    if dt is None:
        dt = datetime.now(timezone.utc)
    day = dt.strftime("%Y-%m-%d")
    p = DEPTH_ROOT / venue / symbol / f"{day}.ndjson"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def append_depth(venue: str, symbol: str, bids: List[List[float]], asks: List[List[float]], seq: int | None =None, ts: datetime | None =None) -> Path:
    if ts is None:
        ts = datetime.now(timezone.utc)
    path = depth_path(venue, symbol, ts)
    envelope = {
        "timestamp": ts.isoformat(),
        "venue": venue,
        "symbol": symbol,
        "bids": bids,
        "asks": asks,
        "seq": seq,
        "note": "DAT-17 depth snapshot"
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(envelope, ensure_ascii=False) + "\n")
    return path

def list_depth(venue: str | None =None, symbol: str | None =None, since_days: int =30) -> List[Path]:
    if not DEPTH_ROOT.exists():
        return []
    # pattern depends on filters
    if venue and symbol:
        pattern = DEPTH_ROOT / venue / symbol / "*.ndjson"
        files = list(pattern.parent.glob("*.ndjson"))
    elif venue:
        files = list((DEPTH_ROOT / venue).rglob("*.ndjson"))
    else:
        files = list(DEPTH_ROOT.rglob("*.ndjson"))
    out=[]
    for p in files:
        try:
            age_days = (time.time() - p.stat().st_mtime) / 86400
            if age_days <= since_days:
                out.append(p)
        except Exception:
            continue
    return sorted(out)

def purge_expired(retention_days: int =30) -> int:
    deleted=0
    for p in DEPTH_ROOT.rglob("*.ndjson*"):
        try:
            age_days = (time.time() - p.stat().st_mtime) / 86400
            if age_days > retention_days:
                p.unlink(missing_ok=True)
                deleted+=1
        except Exception:
            continue
    return deleted

def depth_stats(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "lines":0, "bytes":0}
    lines=0
    total=0
    try:
        with open(path) as f:
            for line in f:
                lines+=1
                total+=len(line.encode())
        # check latest snapshot freshness
        with open(path) as f:
            last = None
            for line in f:
                last = line
            if last:
                j=json.loads(last)
                ts = j.get("timestamp")
            else:
                ts=None
    except Exception as e:
        return {"path": str(path), "lines": lines, "error": str(e)}
    return {"path": str(path), "lines": lines, "bytes": total, "latest_timestamp": ts if 'ts' in locals() else None, "note": "depth stats 30d retention"}
