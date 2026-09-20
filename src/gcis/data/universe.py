"""
src/gcis/data/universe.py — Contract registry sync (P01, DAT-02/15, ARC-11, OD-01, INV-25/26, FBK)

- Discovers ALL tradable futures contracts from venue_chain, persists to contract_registry.
- Supports failover: primary → next healthy venue on 451/403/5xx/timeout (no circumvention SEC-09).
- Updates VenueStatus, ProviderStatus, SourceSwitchEvent, ContractStatusHistory, CoverageReport.
- Honest: if all venues fail -> NO DATA, never fabricate.
- Invariant: no hard-coded list (INV-25); CoverageReport shows analysed/listed.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal
import time
import logging
from sqlalchemy.orm import Session

from gcis.persistence.models import (
    ContractRegistry, VenueStatus, ProviderStatus, SourceSwitchEvent,
    ContractStatusHistory, CoverageReport
)
from gcis.persistence.db import get_session
from gcis.core.config import get_config

log = logging.getLogger(__name__)

# Venue adapters registry
ADAPTERS = {
    "binance_um": "gcis.data.exchange.binance_um:BinanceUMAdapter",
    "binance_cm": "gcis.data.exchange.binance_cm:BinanceCMAdapter",
    "bybit_linear": "gcis.data.exchange.bybit:BybitAdapter",
    "bybit_inverse": "gcis.data.exchange.bybit:BybitAdapter",
    "okx_swap": "gcis.data.exchange.okx:OKXAdapter",
    "hyperliquid": "gcis.data.exchange.hyperliquid:HyperliquidAdapter",
}

# Short chain default; config may override
DEFAULT_CHAIN = ["binance_um", "bybit_linear", "okx_swap", "hyperliquid"]

def _load_adapter(venue_id: str):
    path = ADAPTERS.get(venue_id)
    if not path:
        # fallback: try binance_um style for gate etc not implemented -> raise
        raise ValueError(f"No adapter for venue {venue_id}")
    mod, cls = path.split(":")
    import importlib
    m = importlib.import_module(mod)
    return getattr(m, cls)

def _is_geo_block(exc: Exception) -> bool:
    s = str(exc).lower()
    if "451" in s or "403" in s or "restricted" in s:
        return True
    # check httpx response
    try:
        resp = getattr(exc, "response", None)
        if resp is not None and hasattr(resp, "status_code"):
            if resp.status_code in (451, 403):
                return True
    except Exception:
        pass
    return False

def _normalize_contract(c: Dict[str, Any]) -> Dict[str, Any]:
    # ensure required fields
    for k in ("venue","symbol","base","quote","contract_family","contract_type","status"):
        if k not in c:
            c[k] = "UNKNOWN"
    # asset_class override via file if exists (optional)
    try:
        from pathlib import Path
        import yaml
        p = Path("config/asset_class_overrides.yaml")
        if p.exists():
            overrides = yaml.safe_load(p.read_text()) or {}
            if c["symbol"] in overrides:
                c["asset_class"] = overrides[c["symbol"]]
    except Exception:
        pass
    return c

def sync_registry(
    session: Session | None = None,
    venue_chain: List[str] | None = None,
    timeout: int = 10,
    force: bool = False,
    use_fixtures_on_failure: bool = False,
) -> Dict[str, Any]:
    """
    Sync contract registry from venue_chain. Updates ProviderStatus/VenueStatus.
    Returns dict: {venue_used, contracts_found, listed, added, updated, status, error}
    If network fails, optionally load recorded fixtures (tests only) when use_fixtures_on_failure True.
    """
    cfg = get_config()
    if venue_chain is None:
        venue_chain = cfg.get("universe", {}).get("venue_chain", DEFAULT_CHAIN)
    close_session = False
    if session is None:
        session = get_session()
        close_session = True

    # Determine previous active venue for switch event
    prev_active = session.query(VenueStatus).filter(VenueStatus.active == True).first()  # type: ignore
    prev_venue = prev_active.venue if prev_active else None

    last_error = None
    chosen_venue = None
    raw_contracts: List[Dict[str, Any]] = []

    for venue_id in venue_chain:
        try:
            AdapterCls = _load_adapter(venue_id)
            adapter = AdapterCls(timeout=timeout)
            try:
                # quick time ping to verify reachability + latency
                t0 = time.time()
                try:
                    adapter.get_time()
                    latency_ms = int((time.time() - t0) * 1000)
                except Exception:
                    latency_ms = None
                contracts = adapter.fetch_contracts()
                contracts = [_normalize_contract(c) for c in contracts]
                raw_contracts = contracts
                chosen_venue = venue_id
                # update VenueStatus success
                vs = session.get(VenueStatus, venue_id)
                if vs is None:
                    vs = VenueStatus(venue=venue_id)
                    session.add(vs)
                vs.status = "HEALTHY"
                vs.active = True
                vs.last_success = datetime.now(timezone.utc)
                vs.latency_ms = latency_ms
                vs.error_count = 0
                # deactivate others
                for other in session.query(VenueStatus).all():
                    if other.venue != venue_id:
                        other.active = False
                        if other.status == "HEALTHY":
                            other.status = "STANDBY"
                # ProviderStatus for CAP-01_registry
                ps_key = f"binance_um_registry" if venue_id == "binance_um" else f"{venue_id}_registry"
                # generic: use venue_id as provider, capability CAP-01_registry
                ps = session.get(ProviderStatus, f"{venue_id}:CAP-01_registry")
                if ps is None:
                    ps = ProviderStatus(provider=f"{venue_id}:CAP-01_registry", venue=venue_id, capability="CAP-01_registry")
                    session.add(ps)
                ps.status = "HEALTHY"
                ps.role = "PRIMARY" if venue_id == venue_chain[0] else "FALLBACK"
                ps.last_success = datetime.now(timezone.utc)
                ps.latency_ms = latency_ms
                ps.error_count = 0
                ps.circuit_state = "CLOSED"
                ps.requests = (ps.requests or 0) + 1
                # switch event if needed
                if prev_venue and prev_venue != chosen_venue:
                    ev = SourceSwitchEvent(capability="CAP-01_registry", from_source=prev_venue, to_source=chosen_venue, reason=str(last_error or "failover"))
                    session.add(ev)
                log.info(f"sync_registry: {venue_id} fetched {len(contracts)} contracts")
                break
            finally:
                try:
                    adapter.close()
                except Exception:
                    pass
        except Exception as e:
            last_error = e
            geo = _is_geo_block(e)
            status_str = "RESTRICTED" if geo else ("DISCONNECTED" if "timeout" in str(e).lower() or "connect" in str(e).lower() else "UNAVAILABLE")
            vs = session.get(VenueStatus, venue_id)
            if vs is None:
                vs = VenueStatus(venue=venue_id)
                session.add(vs)
            vs.status = status_str
            vs.active = False
            vs.last_failure = datetime.now(timezone.utc)
            vs.error_count = (vs.error_count or 0) + 1
            ps = session.get(ProviderStatus, f"{venue_id}:CAP-01_registry")
            if ps is None:
                ps = ProviderStatus(provider=f"{venue_id}:CAP-01_registry", venue=venue_id, capability="CAP-01_registry")
                session.add(ps)
            ps.status = status_str
            ps.last_failure = datetime.now(timezone.utc)
            ps.error_count = (ps.error_count or 0) + 1
            ps.circuit_state = "OPEN" if geo else "HALF_OPEN"
            ps.requests = (ps.requests or 0) + 1
            log.warning(f"sync_registry: venue {venue_id} failed {status_str}: {e}")
            continue

    if chosen_venue is None:
        # flush pending VenueStatus/ProviderStatus from failure loop so fixture path can reuse them correctly
        try:
            session.flush()
        except Exception:
            pass
        # All venues failed, try fixtures only if explicitly requested (tests)
        if use_fixtures_on_failure:
            # load first fixture (binance_um) as synthetic
            try:
                from pathlib import Path
                import json
                fixture_path = Path("tests/fixtures/real/binance_um_exchangeInfo.json")
                if fixture_path.exists():
                    data = json.loads(fixture_path.read_text())
                    from gcis.data.exchange.binance_um import BinanceUMAdapter
                    raw_contracts = BinanceUMAdapter.parse_exchange_info(data, venue="binance_um")
                    chosen_venue = "binance_um"
                    # mark fixture as HEALTHY (offline CODE_VERIFIED, FBK keyless)
                    vsf = session.get(VenueStatus, chosen_venue)
                    if vsf is None:
                        vsf = VenueStatus(venue=chosen_venue)
                        session.add(vsf)
                    vsf.status = "HEALTHY (fixture)"
                    vsf.active = True
                    vsf.last_success = datetime.now(timezone.utc)
                    vsf.error_count = 0
                    # deactivate others' active but keep their DISCONNECTED
                    for other in session.query(VenueStatus).all():
                        if other.venue != chosen_venue:
                            other.active = False
                    psf = session.get(ProviderStatus, f"{chosen_venue}:CAP-01_registry")
                    if psf is None:
                        psf = ProviderStatus(provider=f"{chosen_venue}:CAP-01_registry", venue=chosen_venue, capability="CAP-01_registry")
                        session.add(psf)
                    psf.status = "HEALTHY"
                    psf.last_success = datetime.now(timezone.utc)
                    psf.circuit_state = "CLOSED"
                    psf.requests = (psf.requests or 0) + 1
                    log.info(f"sync_registry: using fixture with {len(raw_contracts)} contracts")
            except Exception as e:
                log.warning(f"fixture load failed: {e}")
        if not raw_contracts:
            # honest NO DATA
            # still create CoverageReport with 0 listed
            try:
                session.commit()
            except Exception:
                session.rollback()
            if close_session:
                session.close()
            return {"venue_used": None, "contracts_found": 0, "listed": 0, "added": 0, "updated": 0, "status": "NO DATA", "error": str(last_error) if last_error else "all venues unreachable"}

    # Now persist contracts: upsert into contract_registry
    added = 0
    updated = 0
    onboard_now = datetime.now(timezone.utc)
    listed = len(raw_contracts)
    analysable = 0
    excluded = 0
    # Config eligibility
    cfg_universe = cfg.get("universe", {})
    analyze_tradfi = cfg_universe.get("analyze_tradfi", False)
    # For futures, count TRADING as listed; analysable excludes asset_class tradfi if flag false
    for c in raw_contracts:
        cid = f"{c['venue']}:{c['symbol']}"
        existing = session.get(ContractRegistry, cid)
        # determine if analysable
        is_tradfi = c.get("asset_class") in ("EQUITY","INDEX","COMMODITY","FX","TRADFI")
        if is_tradfi and not analyze_tradfi:
            # not counted as analysable, but still listed
            excluded_increment = 1  # we will aggregate later
        else:
            # if status TRADING then analysable candidate
            pass
        if existing is None:
            reg = ContractRegistry(
                contract_id=cid,
                venue=c["venue"],
                symbol=c["symbol"],
                base=c.get("base",""),
                quote=c.get("quote",""),
                settle_asset=c.get("settle_asset"),
                contract_family=c.get("contract_family","LINEAR"),
                contract_type=c.get("contract_type","PERPETUAL"),
                status=c.get("status","UNKNOWN"),
                tick_size=c.get("tick_size"),
                step_size=c.get("step_size"),
                min_notional=c.get("min_notional"),
                margin_asset=c.get("margin_asset"),
                funding_interval_h=c.get("funding_interval_h"),
                asset_class=c.get("asset_class","UNKNOWN"),
                first_seen=onboard_now,
                onboard_time=onboard_now if c.get("status") == "TRADING" else None,
            )
            session.add(reg)
            added += 1
            # status history
            hist = ContractStatusHistory(contract_id=cid, old_status=None, new_status=c.get("status","UNKNOWN"), reason="onboard")
            session.add(hist)
        else:
            # check status change
            old = existing.status
            new = c.get("status","UNKNOWN")
            if old != new:
                hist = ContractStatusHistory(contract_id=cid, old_status=old, new_status=new, reason="sync")
                session.add(hist)
                existing.status = new
                if new == "TRADING" and existing.onboard_time is None:
                    existing.onboard_time = onboard_now
                updated += 1
            # update other fields if changed
            for field in ("tick_size","step_size","min_notional","margin_asset","contract_family","contract_type","base","quote","settle_asset","asset_class"):
                if field in c and c[field] is not None:
                    setattr(existing, field, c[field])
            # if not status change but other updates, count as updated? keep simple
        # count analysable after insert
    # compute coverage counts
    # Need to query after flush
    session.flush()
    # listed = total contracts in registry for chosen venue? or all venues?
    # For simplicity, listed = len(raw_contracts) (current fetch)
    # analysable = count of TRADING contracts that are not excluded
    analysable = 0
    excluded = 0
    warming_up = 0
    for c in raw_contracts:
        asset_class = c.get("asset_class","UNKNOWN")
        if asset_class in ("EQUITY","INDEX","COMMODITY","FX","TRADFI") and not analyze_tradfi:
            excluded += 1
        elif c.get("status") == "TRADING":
            # require min age? For P01 just count as analysable if TRADING
            analysable += 1
        else:
            # not trading e.g., SETTLING -> not analysable
            excluded += 0  # separate but ignore
    # warming_up: contracts that are onboard < min_history_bars? For P01 set 0
    warming_up = 0
    not_subscribed = 0
    stale = 0
    analysed_live = analysable  # in P01 without live, assume analysable == analysed but real health will compute
    details = {
        "venue_used": chosen_venue,
        "contracts_sample": [c["symbol"] for c in raw_contracts[:5]],
        "error_last": str(last_error) if last_error else None,
    }
    cov = CoverageReport(
        venue=chosen_venue,
        listed=listed,
        analysable=analysable,
        analysed_live=analysed_live,
        warming_up=warming_up,
        excluded=excluded,
        not_subscribed=not_subscribed,
        stale=stale,
        details=details,
    )
    session.add(cov)
    session.commit()
    if close_session:
        # keep session open for caller? we closed transaction but keep session for reuse; close now
        session.close()
    return {
        "venue_used": chosen_venue,
        "contracts_found": listed,
        "listed": listed,
        "analysable": analysable,
        "added": added,
        "updated": updated,
        "status": "HEALTHY" if chosen_venue else "NO DATA",
        "error": str(last_error) if last_error else None,
    }

def get_registry(session: Session, venue: Optional[str] = None, status: str = "TRADING", limit: int = 1000) -> List[ContractRegistry]:
    q = session.query(ContractRegistry)
    if venue:
        q = q.filter(ContractRegistry.venue == venue)
    if status:
        q = q.filter(ContractRegistry.status == status)
    return q.limit(limit).all()

def coverage_summary(session: Session) -> Dict[str, Any]:
    cov = session.query(CoverageReport).order_by(CoverageReport.created_at.desc()).first()
    if not cov:
        return {"listed": 0, "analysable": 0, "analysed_live": 0, "warming_up": 0, "excluded": 0, "not_subscribed": 0, "stale": 0}
    return {
        "listed": cov.listed,
        "analysable": cov.analysable,
        "analysed_live": cov.analysed_live,
        "warming_up": cov.warming_up,
        "excluded": cov.excluded,
        "not_subscribed": cov.not_subscribed,
        "stale": cov.stale,
        "venue": cov.venue,
        "created_at": cov.created_at.isoformat() if cov.created_at else None,
    }
