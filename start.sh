#!/bin/bash
echo "[GCIS] Starting on 0.0.0.0:8501 (preview friendly)..."
python3 -m gcis.cli preflight || true
streamlit run src/gcis/app/streamlit_app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true --server.enableXsrfProtection true
