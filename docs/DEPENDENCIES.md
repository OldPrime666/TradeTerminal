# DEPENDENCIES.md

Every dependency pinned exact == in pyproject.toml; license + purpose recorded.

| Package | Version | License | Purpose | Maintained | Py3.13 wheels | Windows |
|---------|---------|---------|---------|------------|----------------|---------|
| streamlit | 1.39.1 | Apache-2.0 | Operator terminal (UIX) | yes | check | yes |
| plotly | 5.24.1 | MIT | Charts (UIX-07) | yes | yes | yes |
| pandas | 2.2.3 | BSD-3 | Market data frames | yes | yes | yes |
| numpy | 1.26.4 | BSD-3 | Indicators (ANA-02) | yes | yes | yes |
| scipy | 1.14.1 | BSD | Quant stats | yes | yes | yes |
| scikit-learn | 1.5.2 | BSD | Tier B logistic (PRB-02) | yes | yes | yes |
| SQLAlchemy | 2.0.36 | MIT | Persistence (ARC-07) | yes | yes | yes |
| alembic | 1.14.1 | MIT | Migrations | yes | yes | yes |
| psycopg | 3.2.4 | LGPL-3 | PostgreSQL driver | yes | yes | yes |
| pydantic | 2.10.6 | MIT | Config validation | yes | yes | yes |
| pydantic-settings | 2.7.0 | MIT | Env settings | yes | yes | yes |
| PyYAML | 6.0.2 | MIT | Layered YAML config | yes | yes | yes |
| httpx | 0.27.2 | BSD | REST gateway (ARC-11) | yes | yes | yes |
| websockets | 13.1 | BSD | WS transport (DAT-04) | yes | yes | yes |
| tenacity | 9.0.0 | Apache-2.0 | Retry w jitter | yes | yes | yes |
| pyarrow | 17.0.0 | Apache-2.0 | Parquet segments (ARC-07) | yes | yes | yes |
| duckdb | 1.1.3 | MIT | Research Parquet queries | yes | yes | yes |
| zstandard | 0.23.0 | BSD | NDJSON+zstd recorder | yes | yes | yes |
| python-ulid | 1.1.0 | MIT | ULID ids (INV-08) | yes | yes | yes |
| tzdata | 2024.2 | Apache-2.0 | Windows tz DB (ARC-01) | yes | yes | yes |
| keyring | 25.5.0 | MIT/PSF | OS credential store (INV-15) | yes | yes | yes |

Dev: pytest 8.3.4, pytest-asyncio 0.24, pytest-cov 6.0, hypothesis 6.123, ruff 0.8.4, mypy 1.13, bandit 1.8.3, pip-audit 2.7.3, import-linter 2.2, pandas-ta-classic 0.4.47 (oracle only, dev-only per ARC-01).

Indicators implemented in-house per ANA-02; pandas-ta-classic only as test oracle — never imported in runtime.

pip-audit status: UNVERIFIED_ENV if PyPI/network blocked; otherwise run in `verify --full`.
