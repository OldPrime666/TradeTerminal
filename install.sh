#!/bin/bash
set -e
echo "[GCIS] Installing (Linux)..."
python3 -m pip install --upgrade pip
pip install -e . 2>&1 | tail -n 20
mkdir -p var/archive var/raw logs
python3 -m gcis.cli preflight || echo "[WARN] Preflight issues (NO DATA honest)"
echo "[GCIS] Install done. Run: ./start.sh"
