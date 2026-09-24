# SANDBOX_CAPABILITY_MATRIX

| Capability | Available? | Evidence |
|---|---|---|
| Python runtime | YES | 3.11 |
| Project deps (/tmp/pip) | YES | Verify PASSED 224 |
| SQLite (var/gcis.db) | YES | c9d8e7f6a5b4 head |
| PostgreSQL | NO | UNVERIFIED_ENV - sandbox no postgres |
| Local filesystem | YES | /tmp/pip, /tmp/gcis-data |
| Process spawning | YES | TransportManager, Streamlit 8501 |
| multiprocessing | YES | supervisor |
| websocket network | UNVERIFIED_ENV | Binance WS blocked in sandbox (NO DATA honest) |
| public Binance REST | UNVERIFIED_ENV | fapi blocked, fixture fallback |
| other venue REST/WS | UNVERIFIED_ENV | bybit/okx/hyperliquid UNVERIFIED_ENV |
| workspace storage 128MB | LIMITED | use /tmp/pip outside snapshot |
| RAM | YES | streamlit 5% |
