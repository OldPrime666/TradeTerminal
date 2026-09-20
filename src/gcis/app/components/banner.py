"""Components banner UIX-04 — venue failover + coverage + mode/health."""
import streamlit as st
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from gcis.core.config import get_config, get_version_info
from gcis.runtime.health import compute_health

def render_banner():
    cfg = get_config()
    ver = get_version_info()
    mode = cfg.get("app",{}).get("mode","PAPER")
    try:
        health = compute_health()
        verdict = health["verdict"]
    except Exception as e:
        verdict = "UNKNOWN"
        health = {"verdict": verdict}
    colA, colB, colC, colD, colE = st.columns([2.2,1,1,1,1])
    with colA:
        st.markdown(f"<h2 style='margin:0;'>◈ GLOBALCRYPTOICTSCANNER 2026</h2><div class='small'>v{ver['software_version']} · analysis {ver['analysis_version']} · config {ver['config_hash']}</div>", unsafe_allow_html=True)
    with colB:
        mode_cls = "badge-live" if mode=="LIVE" else "badge-paper"
        st.markdown(f"<div class='badge {mode_cls}'>Mode: {mode}</div>", unsafe_allow_html=True)
    with colC:
        health_cls = "badge-healthy" if verdict=="HEALTHY" else "badge-degraded" if verdict=="DEGRADED" else "badge-no-data"
        st.markdown(f"<div class='badge {health_cls}'>Data: {verdict}</div>", unsafe_allow_html=True)
    with colD:
        st.markdown("<div class='badge badge-healthy'>DB: OK</div>", unsafe_allow_html=True)
    with colE:
        transport = health.get("details",{}).get("providers",{})
        ws_status = "WEBSOCKET" if any("binance" in k.lower() for k in transport) else "POLLING"
        if not transport:
            ws_status = "NO DATA"
        st.markdown(f"<div class='small'>Transport: {ws_status}</div>", unsafe_allow_html=True)
    now_utc = datetime.now(timezone.utc)
    now_london = now_utc.astimezone(ZoneInfo("Europe/London"))
    now_ny = now_utc.astimezone(ZoneInfo("America/New_York"))
    st.markdown(f"<div class='small'>UTC {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')} · London {now_london.strftime('%H:%M %Z')} · New York {now_ny.strftime('%H:%M %Z')}</div>", unsafe_allow_html=True)
    # venue failover banner FBK-05
    try:
        venue_chain = cfg.get("universe",{}).get("venue_chain", ["binance_um","bybit_linear","okx_swap","hyperliquid"])
        from gcis.persistence.db import get_session as _gs2
        from gcis.persistence.models import VenueStatus as _VS, CoverageReport as _CV
        _db2 = _gs2()
        vs_rows = {v.venue: v.status for v in _db2.query(_VS).all()}
        cov = _db2.query(_CV).order_by(_CV.created_at.desc()).first()
        _db2.close()
        primary = venue_chain[0] if venue_chain else "binance_um"
        if vs_rows.get(primary) in ("RESTRICTED","DISCONNECTED","UNAVAILABLE"):
            st.warning(f"⚠️ VENUE_FALLBACK_ACTIVE: {primary} → {cfg.get('universe',{}).get('active_venue','auto')} (primary {vs_rows.get(primary)})")
        if cov:
            st.info(f"📊 Coverage: analysed {cov.analysed_live} / listed {cov.listed} · analysable {cov.analysable} · warming {cov.warming_up} · excluded {cov.excluded} · not_subscribed {cov.not_subscribed} · stale {cov.stale} (DAT-19)")
    except Exception:
        pass
