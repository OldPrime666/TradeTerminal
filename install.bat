@echo off
REM GCIS install.bat — thin wrapper (ARC-16)
echo [GCIS] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.in 2>nul || pip install -e . || pip install -e .[dev]
echo [GCIS] Creating var dirs...
mkdir var\archive 2>nul
mkdir var\raw 2>nul
mkdir logs 2>nul
echo [GCIS] Running preflight...
python -m gcis.cli preflight
if errorlevel 1 echo [WARN] Preflight reported issues — check output (NO DATA is honest if Binance blocked)
echo [GCIS] Install done. Next: start.bat
