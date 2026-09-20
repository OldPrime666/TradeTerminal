@echo off
REM GCIS reset_paper.bat — guarded destructive (OPS-07)
echo [GCIS] Reset PAPER account, orders, fills, positions, daily risk state
set /p CONFIRM="Type RESET PAPER to confirm: "
if not "%CONFIRM%"=="RESET PAPER" (
  echo Cancelled.
  exit /b 1
)
python -c "from gcis.persistence.db import get_session, init_db; init_db(); from gcis.persistence.models import PaperAccount, Position, ExecutionIntent; s=get_session(); print('Reset paper — deleting'); s.query(PaperAccount).delete(); s.query(Position).delete(); s.query(ExecutionIntent).delete(); s.commit(); print('Done')"
echo [GCIS] Paper reset done. Backup was taken via backup.bat if needed.
