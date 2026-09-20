@echo off
REM GCIS reset_database.bat — guarded destructive (OPS-07)
echo [GCIS] Reset DATABASE — will delete all tables. Requires typed confirmation and backup.
set /p CONFIRM="Type RESET DATABASE to confirm: "
if not "%CONFIRM%"=="RESET DATABASE" (
  echo Cancelled.
  exit /b 1
)
python -c "from gcis.persistence.db import get_engine; from gcis.persistence.models import Base; e=get_engine(); Base.metadata.drop_all(bind=e); Base.metadata.create_all(bind=e); print('Database reset complete')"
echo [GCIS] Database reset done.
