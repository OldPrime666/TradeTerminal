@echo off
REM GCIS start.bat — thin wrapper, starts Streamlit on 127.0.0.1
echo [GCIS] Starting GLOBALCRYPTOICTSCANNER 2026 — PAPER mode...
python -m gcis.cli preflight
streamlit run src/gcis/app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
