import streamlit as st
from gcis.app.components.charts import render_candles
from gcis.persistence.db import get_session
from gcis.persistence.models import Candle
import pandas as pd
st.header("Charts — Plotly from engine state + as-of toggle capped 800 UIX-07")
symbol=st.selectbox("Symbol charts", ["BTCUSDT"])
timeframe=st.selectbox("TF", ["15m","1h"])
try:
    db=get_session()
    candles=db.query(Candle).filter(Candle.symbol==symbol, Candle.timeframe==timeframe).order_by(Candle.close_time.desc()).limit(800).all()
    db.close()
    if candles:
        df=pd.DataFrame([{"open_time":c.open_time,"open":float(c.open),"high":float(c.high),"low":float(c.low),"close":float(c.close)} for c in reversed(candles)])
        render_candles(df, symbol, timeframe)
    else:
        st.info("NO DATA — no candles")
except Exception as e:
    st.error(str(e))
