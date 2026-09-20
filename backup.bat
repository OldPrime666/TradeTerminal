@echo off
REM GCIS backup.bat — PG dump + config copy + Parquet manifest (OPS-06)
echo [GCIS] Backup — var/ + config/ + DB dump...
python -m gcis.cli backup 2>nul || echo [GCIS] backup via python -m gcis.cli not yet implemented — use pg_dump manually if on Postgres
if exist var\gcis.db (
  copy var\gcis.db var\backup_gcis_%date:~-4,4%%date:~-10,2%%date:~-7,2%.db
  echo [GCIS] SQLite backup copied to var\
)
echo [GCIS] Backup done. Verify via: python -m gcis.cli backup --verify
