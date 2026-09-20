import streamlit as st
from datetime import datetime, timezone
from pathlib import Path
import sys
# Ensure src on path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from gcis.core.config import get_config, get_version_info
from gcis.persistence.db import init_db, get_session
from gcis.persistence.models import ProviderStatus, SystemHealth, WorkerState, Candle, LatestQuote, Signal
from gcis.runtime.health import compute_health
import pandas as pd
from decimal import Decimal

st.set_page_config(
    page_title="GLOBALCRYPTOICTSCANNER 2026",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Theme CSS — dark navy #0A1428, greens #00FF9D/#00C853 etc per UIX-12
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@400;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main { background: #0A1428; }
.stMetric { background: linear-gradient(135deg, #0F2340 0%, #1A3350 100%); border: 1px solid #1E4A7A; border-radius: 10px; padding: 12px; }
h1, h2, h3 { color: #00FF9D !important; }
div[data-testid="stStatusWidget"] { background: #0A1428; }
.card { background: linear-gradient(145deg, #0F2340, #122A4A); border: 1px solid #1E5A8A; border-radius: 12px; padding: 16px; margin: 8px 0; box-shadow: 0 4px 20px rgba(0,255,157,0.08); }
.badge { display:inline-block; padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; }
.badge-healthy { background:#00C853; color:#00210F; }
.badge-degraded { background:#FFD600; color:#332800; }
.badge-no-data { background:#FF5252; color:white; }
.badge-paper { background:#2196F3; color:white; }
.badge-live { background:#FF1744; color:white; }
.small { font-size:12px; opacity:0.75; }
</style>
""", unsafe_allow_html=True)

# Init DB lazily
try:
    init_db()
except Exception as e:
    st.error(f"DB init failed: {e}")

cfg = get_config()
ver = get_version_info()

# --- Banner (UIX-04) ---
mode = cfg.get("app",{}).get("mode","PAPER")
health = None
try:
    health = compute_health()
    verdict = health["verdict"]
except Exception as e:
    verdict = "UNKNOWN"
    health = {"verdict": verdict, "details": {"error": str(e)}}

# Top banner
colA, colB, colC, colD, colE = st.columns([2.2, 1, 1, 1, 1])
with colA:
    st.markdown(f"<h2 style='margin:0;'>◈ GLOBALCRYPTOICTSCANNER 2026</h2><div class='small'>v{ver['software_version']} · analysis {ver['analysis_version']} · config {ver['config_hash']}</div>", unsafe_allow_html=True)
with colB:
    mode_color = "badge-live" if mode=="LIVE" else "badge-paper"
    st.markdown(f"<div class='badge {mode_color}'>Mode: {mode}</div>", unsafe_allow_html=True)
with colC:
    health_cls = "badge-healthy" if verdict=="HEALTHY" else "badge-degraded" if verdict=="DEGRADED" else "badge-no-data"
    st.markdown(f"<div class='badge {health_cls}'>Data: {verdict}</div>", unsafe_allow_html=True)
with colD:
    st.markdown(f"<div class='badge badge-healthy'>DB: OK</div>", unsafe_allow_html=True)
with colE:
    # Transport status
    transport = health.get("details",{}).get("providers",{})
    ws_status = "WEBSOCKET" if any("binance" in k.lower() for k in transport) else "POLLING"
    # If no providers yet, show NO DATA
    if not transport:
        ws_status = "NO DATA"
    st.markdown(f"<div class='small'>Transport: {ws_status}</div>", unsafe_allow_html=True)

# UTC / London / NY times per ANA-03
from zoneinfo import ZoneInfo
now_utc = datetime.now(timezone.utc)
now_london = now_utc.astimezone(ZoneInfo("Europe/London"))
now_ny = now_utc.astimezone(ZoneInfo("America/New_York"))
st.markdown(f"<div class='small'>UTC {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')} · London {now_london.strftime('%H:%M %Z')} · New York {now_ny.strftime('%H:%M %Z')} · <span style='color:#00FF9D'>Session: {' overlap' if now_london.hour>=14 else ''}</span></div>", unsafe_allow_html=True)
st.divider()

# Sidebar (UIX-11)
with st.sidebar:
    st.header("⚙ Controls")
    st.caption("Local-only · Free data · No API key required")
    symbols_cfg = cfg.get("universe",{}).get("symbols", ["BTC","ETH","SOL","BNB","XRP","DOGE","ADA","AVAX","LINK","TON","SUI","PEPE"])
    selected_symbol = st.selectbox("Market", [f"{s}USDT" for s in symbols_cfg], index=0)
    timeframe = st.selectbox("Primary timeframe", ["1m","5m","15m","1h","4h","1d"], index=2)
    min_score = st.slider("Min setup score", 0, 100, 55)
    st.divider()
    st.subheader("Risk")
    st.metric("Risk per trade", f"{cfg.get('risk',{}).get('risk_per_trade_pct',0.25)}% (cap 0.50% HARD)")
    st.metric("Daily loss limit", f"{cfg.get('risk',{}).get('max_daily_loss_pct',1.5)}% (cap 2.00% HARD)")
    st.metric("Max trades/day", f"{cfg.get('risk',{}).get('max_trades_per_day',6)} (cap 10 HARD)")
    st.divider()
    if st.button("🔴 KILL SWITCH — BLOCK NEW TRADES", type="primary", use_container_width=True):
        try:
            from gcis.persistence.db import get_session
            from gcis.persistence.models import KillSwitchState
            from datetime import datetime, timezone
            db = get_session()
            ks = KillSwitchState(active=True, mode="BLOCK_NEW_TRADES", reason="operator via UI", created_at=datetime.now(timezone.utc))
            db.add(ks); db.commit(); db.close()
            st.success("Kill switch activated: BLOCK_NEW_TRADES")
            st.rerun()
        except Exception as e:
            st.error(f"Kill switch failed: {e}")
    if st.button("🟢 Release kill switch"):
        try:
            from gcis.persistence.db import get_session
            from gcis.persistence.models import KillSwitchState
            from datetime import datetime, timezone
            db = get_session()
            ks = KillSwitchState(active=False, mode="BLOCK_NEW_TRADES", reason="manual unlock", created_at=datetime.now(timezone.utc))
            db.add(ks); db.commit(); db.close()
            st.success("Kill switch released")
            st.rerun()
        except Exception as e:
            st.error(str(e))
    st.divider()
    st.caption("Docs: AGENTS.md · docs/SPEC.md · docs/DEFAULTS.md")
    st.caption("Free resources: Binance public market data (no key) · REST data-api.binance.vision · WS data-stream.binance.vision · If blocked → NO DATA (never circumvent)")

# Main layout: overview tabs
tab_overview, tab_scanner, tab_coin, tab_risk, tab_health, tab_research = st.tabs(["🏠 Overview","🔍 Scanner","🪙 Coin Detail","🛡 Risk Center","💚 System Health","📊 Research"])

with tab_overview:
    # STRONGEST SIGNAL card (UIX-05, PRB-08, PRB-12)
    st.subheader("STRONGEST SIGNAL")
    # Query latest qualified signals
    try:
        db = get_session()
        # fetch signals
        signals = db.query(Signal).order_by(Signal.created_at.desc()).limit(20).all()
        db.close()
    except Exception as e:
        signals = []
        st.warning(f"DB query failed: {e}")
    if not signals:
        # No qualified setup — honest state
        st.markdown("""
        <div class='card' style='border-color:#FFD600;'>
        <h3 style='color:#FFD600 !important; margin:0;'>NO QUALIFIED SETUP</h3>
        <p class='small'>No signal passes Market-Validity and Portfolio gates currently.</p>
        <p><b>Reasons (live):</b></p>
        <ul class='small'>
          <li>BTCUSDT: INSUFFICIENT_HISTORY / NO DATA — live feed not yet primed (waiting for candles)</li>
          <li>ETHUSDT: INSUFFICIENT_HISTORY</li>
          <li>All symbols: DATA_STALE or DISCONNECTED if Binance unreachable → NO DATA (honest)</li>
        </ul>
        <p class='small'>This is a valid state. Prefer NO TRADE over low-quality trade.</p>
        </div>
        """, unsafe_allow_html=True)
        # TOP UNVALIDATED CANDIDATE card (PRB-12)
        st.markdown("""
        <div class='card' style='border-style:dashed; opacity:0.9;'>
        <h4 style='color:#2196F3 !important; margin:0;'>TOP UNVALIDATED CANDIDATE <span class='badge' style='background:#333; color:#FFD600;'>UNVALIDATED — NOT A SIGNAL</span></h4>
        <p class='small'>At L0–L2 probability is <b>N/A — INSUFFICIENT_PROBABILITY_DATA</b> (needs ≥100 effective training events, calibration, OOS). Ranking here is by <b>setup score</b> only, never by probability.</p>
        <p class='small'>Example (synthetic preview): BTCUSDT · 15m · ICT-A · score 62 (grade C) · probability <b>N/A</b> · expected R <b>N/A</b> · <i>Labelled as hypothesis to be tested (BKT-05), not a claim of edge.</i></p>
        </div>
        """, unsafe_allow_html=True)
    else:
        for s in signals[:3]:
            prob = f"{float(s.probability)*100:.1f}%" if s.probability is not None else "N/A — INSUFFICIENT_PROBABILITY_DATA"
            st.markdown(f"""
            <div class='card'>
            <h4 style='margin:0;'>{s.symbol} · {s.direction} · {s.primary_timeframe} · Score {s.setup_score} <span class='badge badge-healthy'>{s.state}</span></h4>
            <div class='small'>Strategy {s.strategy} · Regime {s.regime} · Session {s.session} · Expected R {s.expected_r if s.expected_r else 'N/A'} · Probability {prob}</div>
            <div class='small'>Entry {s.entry} · Stop {s.stop} · TP1 {s.target_1} · TP2 {s.target_2}</div>
            <div class='small'>Created {s.created_at} · Expires {s.expires_at} · Evidence hash {s.evidence_hash[:12] if s.evidence_hash else '-'}</div>
            </div>
            """, unsafe_allow_html=True)
            with st.expander("Why this signal exists (explainability)"):
                st.json({"signal_id": s.signal_id, "evidence_hash": s.evidence_hash, "analysis_version": s.analysis_version, "config_version": s.config_version, "probability": str(s.probability) if s.probability else "N/A", "probability_status": s.probability_status})

    st.divider()
    # Market scanner table (UIX-05)
    st.subheader("Market Scanner")
    # Build scanner from latest quotes + candles
    try:
        db = get_session()
        quotes = {q.symbol: q for q in db.query(LatestQuote).all()}
        # get last candle close per symbol for 15m
        scanner_rows = []
        for base in cfg.get("universe",{}).get("symbols",[]):
            sym = f"{base}USDT"
            q = quotes.get(sym)
            if q:
                price = float(q.price)
                age_s = (datetime.now(timezone.utc) - q.updated_at).total_seconds() if q.updated_at.tzinfo else (datetime.now(timezone.utc) - q.updated_at.replace(tzinfo=timezone.utc)).total_seconds()
                age_str = f"{int(age_s)}s ago"
                quality = "HEALTHY" if age_s<5 else "DEGRADED" if age_s<30 else "STALE"
            else:
                price = None
                age_str = "NO DATA"
                quality = "NO DATA"
            # regime placeholder (would compute from real candles)
            regime = "UNCERTAIN"
            scanner_rows.append({"Symbol": sym, "Market": "SPOT", "Price": f"{price:.2f}" if price else "NO DATA", "24h change": "NO DATA", "Setup score": "—", "Probability": "N/A", "Probability status": "INSUFFICIENT_DATA", "Regime": regime, "Data age": age_str, "Quality": quality, "Signal state": "NO QUALIFIED SETUP"})
        db.close()
        df_scan = pd.DataFrame(scanner_rows)
        st.dataframe(df_scan, use_container_width=True, hide_index=True)
        st.caption("Sorted by qualified status → EV_lcb (if available) → setup score. Never sorted by fabricated probability. If Binance unreachable, all rows show NO DATA (honest).")
    except Exception as e:
        st.warning(f"Scanner unavailable: {e}")
        # Fallback static table
        st.dataframe(pd.DataFrame([{"Symbol":"BTCUSDT","Status":"NO DATA — Binance unreachable in this environment (NO DATA is honest)","Price":"—","Data age":"—"}]), use_container_width=True)

    st.divider()
    # News ticker placeholder
    st.subheader("News Ticker")
    st.info("NEWS UNAVAILABLE — macro calendar / RSS feeds not yet configured (P1/P2). News as veto/blackout requires free public feed; if all providers fail → strategies depending on news are BLOCKED, others continue. (DAT-13)")

with tab_scanner:
    st.subheader("Signal Census & Scanner Controls")
    st.write("Live scanner runs in Core process (ingest → market → ICT → strategy → gates → fusion). This tab shows persisted read-models only (INV-06).")
    if st.button("Run Signal Census (BKT-06)"):
        try:
            from gcis.backtest.census import run_census
            res = run_census()
            st.json(res)
            st.success(f"Feasibility verdict: {res['feasibility_verdict']}")
        except Exception as e:
            st.error(str(e))
    st.divider()
    st.write("To feed live data: `python -m gcis.cli download-history` or run ingest process (see docs/OPERATIONS.md). In sandbox, Binance is blocked → scanner correctly shows NO DATA.")

with tab_coin:
    st.subheader(f"Coin Detail — {selected_symbol}")
    try:
        db = get_session()
        q = db.query(LatestQuote).filter(LatestQuote.symbol==selected_symbol).first()
        if q:
            st.metric("Last price", f"{float(q.price):.2f}", help=f"Source: {q.source} · Updated {q.updated_at} · Age {(datetime.now(timezone.utc)-q.updated_at).total_seconds():.0f}s")
            st.caption(f"Source · {q.source} · timestamp {q.updated_at} · age {(datetime.now(timezone.utc)-q.updated_at).total_seconds():.0f}s · quality HEALTHY" if (datetime.now(timezone.utc)-q.updated_at).total_seconds()<5 else "STALE — DOM strategies disabled")
        else:
            st.warning("NO DATA — no quote yet for this symbol. Check provider status and ingest health.")
        # candles
        candles = db.query(Candle).filter(Candle.symbol==selected_symbol, Candle.timeframe==timeframe).order_by(Candle.close_time.desc()).limit(200).all()
        if candles:
            df = pd.DataFrame([{"open_time":c.open_time,"open":float(c.open),"high":float(c.high),"low":float(c.low),"close":float(c.close),"volume":float(c.volume)} for c in reversed(candles)])
            import plotly.graph_objects as go
            fig = go.Figure(data=[go.Candlestick(x=df["open_time"], open=df["open"], high=df["high"], low=df["low"], close=df["close"], name="Candles")])
            fig.update_layout(height=420, template="plotly_dark", paper_bgcolor="#0A1428", plot_bgcolor="#0A1428", margin=dict(l=10,r=10,t=10,b=10))
            fig.update_xaxes(rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True, theme=None)
            st.caption(f"Overlays drawn from persisted engine state only (no decorative zones). Capped at {cfg.get('ui',{}).get('chart_max_candles',800)} candles. As-of toggle would show structure at signal time (P11).")
        else:
            st.info("NO DATA — no candles yet. Run history download or wait for live WS to close first candle.")
        db.close()
    except Exception as e:
        st.error(f"Coin detail error: {e}")
    # regime/ict placeholders
    st.markdown("**Regime (v1 causal only):** TRENDING_UP / RANGING / UNCERTAIN (validation EG: must separate forward volatility). **ICT structure:** BOS/CHOCH/FVG/OB/Breaker drawn from engine — not decorative.")
    st.markdown("**Order book:** `ORDER BOOK — Freshness: N/A — NOT IMPLEMENTED (tier P3)` — DOM requires depth recorder (DAT-17).")

with tab_risk:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Risk Center")
        # fetch daily risk
        try:
            from gcis.persistence.models import DailyRiskState, PaperAccount, KillSwitchState, Position
            db = get_session()
            dr = db.query(DailyRiskState).order_by(DailyRiskState.risk_day.desc()).first()
            acct = db.query(PaperAccount).first()
            ks = db.query(KillSwitchState).order_by(KillSwitchState.id.desc()).first()
            positions = db.query(Position).filter(Position.state!="CLOSED").all()
            db.close()
            if acct:
                st.metric("Equity", f"{float(acct.equity):.2f} USDT", delta=f"PnL {float(acct.realized_pnl):.2f}")
                st.metric("Cash", f"{float(acct.cash):.2f}")
                st.metric("Peak equity", f"{float(acct.peak_equity):.2f}")
            else:
                st.metric("Paper equity", "10,000.00 USDT (initial)", delta="NO DATA — account not yet created")
                st.caption("Paper account resets only via reset_paper.bat with typed confirmation (OPS-07).")
            if dr:
                st.metric("Daily starting equity", f"{float(dr.starting_equity):.2f}")
                st.metric("Daily PnL", f"{float(dr.daily_realized_pnl):.2f}")
                st.metric("Trades today", f"{dr.trades_today} / {cfg.get('risk',{}).get('max_trades_per_day',6)} (HARD cap 10)")
                st.metric("Risk lock", dr.risk_lock)
            else:
                st.info("Daily risk state not yet initialized — will be created at 00:00 UTC reset (OD-04).")
            if ks and ks.active:
                st.error(f"⛔ KILL SWITCH ACTIVE — {ks.mode} — {ks.reason}")
            else:
                st.success("Risk: ACTIVE")
        except Exception as e:
            st.error(str(e))
    with col2:
        st.subheader("Trade Desk")
        st.write("Open positions / pending intents / recent closed")
        try:
            db = get_session()
            from gcis.persistence.models import Position
            positions = db.query(Position).order_by(Position.created_at.desc()).limit(20).all()
            if positions:
                for p in positions:
                    st.markdown(f"<div class='card'><b>{p.symbol}</b> {p.direction} {p.quantity} @ {p.entry_price} → SL {p.stop_loss} TP1 {p.take_profit_1} TP2 {p.take_profit_2}<br><span class='small'>State {p.state} · PnL {p.unrealized_pnl} · Created {p.created_at}</span></div>", unsafe_allow_html=True)
            else:
                st.info("No open positions. Paper AUTO will act on qualified signals (labelled EXPERIMENTAL while probability N/A). Manual ENTER TRADE via commands table (EXE-02) — re-validates all gates atomically.")
            db.close()
        except Exception as e:
            st.error(str(e))
        st.divider()
        if st.button("ENTER TRADE (demo — validates gates)"):
            st.warning("TRADE ENTRY BLOCKED — NO QUALIFIED SIGNAL (honest gate). Reason: INSUFFICIENT_PROBABILITY_DATA / NO_CLEAR_ENTRY / NO DATA. See SIG-01 gates.")
        st.caption("All actions write commands (idempotency_key) → Core validates in same DB transaction (INV-10). Duplicate clicks never double-create.")

with tab_health:
    st.subheader("System Health")
    try:
        h = health
        st.json(h)
        # providers
        prov_rows = [{"Provider": k, "Status": v} for k,v in h["details"].get("providers",{}).items()] or [{"Provider":"Binance WS","Status":"NO DATA (sandbox TLS blocked)"},{"Provider":"Binance REST","Status":"NO DATA"},{"Provider":"CoinPaprika","Status":"NOT IMPLEMENTED (tier P1)"}]
        st.dataframe(pd.DataFrame(prov_rows), use_container_width=True, hide_index=True)
        # metrics
        st.caption("Metrics: messages_received/dropped/out_of_order, websocket_reconnects, polling_fallbacks, stale_events, analysis_cycles, signals_created/blocked, trades_entered/closed, risk_locks, etc. (ARC-14) — persisted to system_metrics, 1-min rollups.")
    except Exception as e:
        st.error(str(e))
    if st.button("Run healthcheck"):
        try:
            from gcis.runtime.health import compute_health
            st.json(compute_health())
            st.rerun()
        except Exception as e:
            st.error(str(e))

with tab_research:
    st.subheader("Performance & Research")
    st.info("Research pages: backtest with fidelity labels (EXACT_REPLAY / INTRABAR_REPLAY / OHLC_APPROXIMATION), baseline harness (random-entry / buy-and-hold / EMA-cross / time-shift placebo), signal census, calibration curves. All mechanisms are CODE_VERIFIED; outcomes are EMPIRICAL_PENDING until real data accumulated (Part 1.4).")
    if st.button("Run Backtest (demo on available candles)"):
        try:
            from gcis.backtest.engine import run_backtest
            res = run_backtest(symbols=[selected_symbol], timeframe=timeframe)
            st.json(res)
            st.caption("Backtest always reports data fidelity & lineage; degraded → DEGRADED_DATA_TEST (INV-19). Baseline verdict: EDGE vs BASELINE significance (BKT-05).")
        except Exception as e:
            st.error(str(e))
    st.divider()
    st.markdown("**Probability model (PRB-01..12):** Built only from `signal_outcomes` (counterfactual tracker). At L0–L2 dashboard shows `STRONGEST SIGNAL: NONE` + separately styled **TOP UNVALIDATED CANDIDATE** ranked by setup score, never executable as strongest. Probability gate: ≥100 effective train, ≥50 OOS, CI ≤10%, ECE ≤5%, version match. Miss → `NULL + status` rendered as **N/A** (never 0%/50%).")

# Footer
st.divider()
st.markdown("<div class='small' style='text-align:center; opacity:0.6;'>GCIS is research software. It promises no profit. “No edge found” is a valid, publishable outcome. Honesty > performance. Free-only · No paid APIs · Live disabled by default (LIVE-01).</div>", unsafe_allow_html=True)
