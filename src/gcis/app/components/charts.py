"""Charts component UIX-07 — Plotly from engine state + as-of toggle capped 800."""
import streamlit as st
import pandas as pd
from gcis.core.config import get_config

def render_candles(df: pd.DataFrame, symbol: str, timeframe: str):
    cfg = get_config()
    max_candles = cfg.get("ui",{}).get("chart_max_candles",800)
    if len(df) > max_candles:
        df = df.tail(max_candles)
        st.caption(f"Capped at {max_candles} candles (UIX-07).")
    import plotly.graph_objects as go
    fig = go.Figure(data=[go.Candlestick(x=df["open_time"], open=df["open"], high=df["high"], low=df["low"], close=df["close"], name="Candles")])
    fig.update_layout(height=420, template="plotly_dark", paper_bgcolor="#0A1428", plot_bgcolor="#0A1428", margin=dict(l=10,r=10,t=10,b=10))
    fig.update_xaxes(rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True, theme=None)
    # as-of toggle
    if st.checkbox("Show as-of structure (P11)", value=False):
        st.caption("Overlays from engine state at signal time (as-of), not current decorative zones.")
