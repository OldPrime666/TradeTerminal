"""
DAT-16 trade archive — aggTrades archive for VOL and survivorship.
Stores aggTrades to var/trade_archive/<venue>/<symbol>/YYYY-MM-DD.jsonl with dedup id.
Free-only, 30d retention for trades vs unlimited for candles.
"""
from pathlib import Path
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Any

TRADE_ROOT = Path("var/trade_archive")

def trade_path(venue: str, symbol: str, dt: datetime | None = None) -> Path:
    if dt is None:
        dt = datetime.now(timezone.utc)
    day = dt.strftime("%Y-%m-%d")
    p = TRADE_ROOT / venue / symbol / f"{day}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def append_trades(venue: str, symbol: str, trades: List[Dict[str,Any]], dt: datetime | None =None) -> Path:
    """
    trades: list of dicts with keys aggTradeId, price, qty, timestamp, isBuyerMaker
    Dedup by aggTradeId.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    path = trade_path(venue, symbol, dt)
    # dedup existing ids
    existing_ids = set()
    if path.exists():
        try:
            with open(path) as f:
                for line in f:
                    try:
                        j=json.loads(line)
                        existing_ids.add(j.get("aggTradeId"))
                    except: pass
        except: pass
    new = 0
    with open(path, "a") as f:
        for tr in trades:
            tid = tr.get("aggTradeId") or tr.get("id")
            if tid in existing_ids:
                continue
            f.write(json.dumps(tr, ensure_ascii=False) + "\n")
            existing_ids.add(tid)
            new+=1
    return path

def list_trade_archive(venue: str | None =None, symbol: str | None =None, since_days: int =30) -> List[Path]:
    if not TRADE_ROOT.exists():
        return []
    if venue and symbol:
        pattern = TRADE_ROOT / venue / symbol / "*.jsonl"
        files = list(pattern.parent.glob("*.jsonl"))
    elif venue:
        files = list((TRADE_ROOT / venue).rglob("*.jsonl"))
    else:
        files = list(TRADE_ROOT.rglob("*.jsonl"))
    out=[]
    for p in files:
        try:
            age = (time.time() - p.stat().st_mtime)/86400
            if age <= since_days:
                out.append(p)
        except: continue
    return sorted(out)

def trade_archive_stats(venue: str, symbol: str) -> Dict[str,Any]:
    files = list_trade_archive(venue, symbol, since_days=30)
    total_lines=0
    total_bytes=0
    for p in files:
        try:
            with open(p) as f:
                for line in f:
                    total_lines+=1
                    total_bytes+=len(line.encode())
        except: pass
    return {"files": len(files), "trades": total_lines, "bytes": total_bytes, "note": "DAT-16 trade archive 30d"}

def purge_expired(retention_days: int =30) -> int:
    deleted=0
    for p in TRADE_ROOT.rglob("*.jsonl*"):
        try:
            age = (time.time() - p.stat().st_mtime)/86400
            if age > retention_days:
                p.unlink(missing_ok=True)
                deleted+=1
        except: continue
    return deleted
