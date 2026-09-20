import streamlit as st
from gcis.persistence.db import get_session
from gcis.persistence.models import Candle, LatestQuote
import pandas as pd
st.header("Coin Detail — Regime/ICT/Orderbook Freshness UIX-06")
symbol=st.selectbox("Symbol", ["BTCUSDT","ETHUSDT"])
try:
    db=get_session()
    q=db.query(LatestQuote).filter(LatestQuote.symbol==symbol).first()
    if q:
        st.metric("Price", float(q.price))
        st.caption(f"Freshness: {( __import__('datetime').datetime.now(__import__('datetime').timezone.utc)-q.updated_at).total_seconds():.0f}s")
    else:
        st.warning("NO DATA — no quote")
    db.close()
except Exception as e:
    st.error(str(e))
