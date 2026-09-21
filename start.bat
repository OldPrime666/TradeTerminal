@echo off
REM GCIS start.bat — Supervisor + Streamlit (Phase 1) — prefers .venv\Scripts\python.exe
setlocal EnableDelayedExpansion
REM Prefer local venv python/streamlit per Phase 1 spec
set "PY=.venv\Scripts\python.exe"
set "ST=.venv\Scripts\streamlit.exe"
if not exist "%PY%" set "PY=python"
if not exist "%ST%" set "ST=streamlit"
echo [GCIS] GCIS start.bat — D:\Projects\TTAgent — using %PY% and %ST%
REM Show actual mode from config (not hard-coded)
for /f "delims=" %%m in ('%PY% -c "from gcis.core.config import get_config; print(get_config().get('app',{}).get('mode','RESEARCH'))" 2^>nul') do set "MODE=%%m"
if "%MODE%"=="" set "MODE=RESEARCH"
echo [GCIS] Mode: %MODE% (from config/default.yaml — RESEARCH default, PAPER supported, LIVE disabled)
REM Preflight — fail clearly if critical
echo [GCIS] Running preflight...
%PY% -m gcis.cli preflight
if errorlevel 1 (
  echo [GCIS][ERROR] Preflight failed — see above. Not starting Supervisor/UI.
  exit /b 1
)
REM Supervisor — continuous loop (transport|analyzer|risk|paper)
echo [GCIS] Starting Supervisor (transport/analyzer/risk/paper) via %PY% -m gcis.runtime.supervisor ...
start "GCIS Supervisor" /min cmd /c "%PY% -m gcis.runtime.supervisor"
if errorlevel 1 (
  echo [GCIS][ERROR] Supervisor failed to start — see logs/var/logs/supervisor.log
  exit /b 1
)
REM Streamlit UI — shared DB/health
echo [GCIS] Starting Streamlit UI on 127.0.0.1:8501 ...
%ST% run src/gcis/app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
endlocal
