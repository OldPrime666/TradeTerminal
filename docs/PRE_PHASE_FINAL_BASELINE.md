# PRE_PHASE_FINAL_BASELINE — 2026-09-24T12:27:26.540472

Repo HEAD: f4118ea 20/20 prior, DB c9d8e7f6a5b4

## Search hits (top 30)
src/gcis/cli.py:except Exception
src/gcis/app/streamlit_app.py:placeholder
src/gcis/app/components/banner.py:except Exception
src/gcis/app/pages/charts.py:placeholder
src/gcis/app/pages/coin_detail.py:except Exception
src/gcis/app/pages/overview.py:except Exception
src/gcis/app/pages/risk_center.py:except Exception
src/gcis/app/pages/trade_desk.py:except Exception
src/gcis/app/readmodels/overview.py:return None
src/gcis/backtest/baselines.py:stub
src/gcis/backtest/census.py:except Exception
src/gcis/backtest/consistency.py:stub
src/gcis/backtest/engine.py:stub
src/gcis/backtest/fidelity.py:stub
src/gcis/backtest/metrics.py:except:
src/gcis/backtest/monte_carlo.py:except:
src/gcis/backtest/walk_forward.py:except:
src/gcis/core/clock.py:NotImplementedError
src/gcis/core/enums.py:HEALTHY
src/gcis/data/coverage.py:HEALTHY
src/gcis/data/eligibility.py:stub
src/gcis/data/gateway.py:except Exception
src/gcis/data/news.py:stub
src/gcis/data/secondary.py:except Exception
src/gcis/data/time_sync.py:except Exception
src/gcis/data/universe.py:except Exception
src/gcis/data/archive/store.py:return []
src/gcis/data/archive/trade_archive.py:except:
src/gcis/data/exchange/base.py:NotImplementedError
src/gcis/data/exchange/binance.py:api/v3

Total hits: 87

## BUILD_STATE
{
  "implementation_version": "1.0.0",
  "current_phase": "DONE",
  "phases": {
    "P00": "CODE_VERIFIED",
    "P01": "CODE_VERIFIED",
    "P02": "CODE_VERIFIED",
    "P03": "CODE_VERIFIED",
    "P04": "CODE_VERIFIED",
    "P05": "CODE_VERIFIED",
    "P06": "CODE_VERIFIED",
    "P07": "CODE_VERIFIED",
    "P08": "CODE_VERIFIED",
    "P09": "CODE_VERIFIED",
    "P10": "CODE_VERIFIED",
    "P11": "CODE_VERIFIED",
    "P12": "CODE_VERIFIED",
    "P13": "CODE_VERIFIED",
    "P14": "CODE_VERIFIED",
    "P15": "CODE_VERIFIED",
    "P16": "CODE_VERIFIED",
    "P17": "CODE_VERIFIED",
    "P18": "CODE_VERIFIED",
    "P19": "CODE_VERIFIED",
    "P20": "CODE_VERIFIED",
    "P21": "CODE_VERIFIED",
    "P22": "CODE_VERIFIED",
    "P99": "CODE_VERIFIED"
  },
  "environment": {
    "os": "Linux 6.1.158+ (#1 SMP PREEMPT_DYNAMIC Mon May 11 18:48:24 UTC 2026) - Linux-6.1.158+-x86_64-with-glibc2.36",
    "python": "3.11.2 (main, Apr  8 2026, 01:58:00) [GCC 12.2.0]",
    "python_executable": "/usr/bin/python",
    "postgres": "unknown_no_client",
    "network_venues": {
      "binance_um": "tcp_ok_but_tls_failed:SSLZeroReturnError",
      "binance_cm": "tcp_ok_but_tls_failed:SSLZeroReturnError",
      "bybit": "tcp_ok_but_tls_failed:SSLZeroReturnError",
      "okx": "tcp_ok_but_tls_failed:SSLZeroReturnError",
      "hyperliquid": "tcp_ok_but_tls_failed:SSLZeroReturnError",
      "data_binance_vision": "tcp_ok_but_tls_failed:SSLZeroReturnError",
      "public_bybit": "tcp_ok_but_tls_failed:SSLZeroReturnError",
      "coinpaprika": "tcp_ok_but_tls_failed:SSLZeroReturnError",
      "alternative_me": "tcp_ok_but_tls_failed:SSLZeroReturnError"
    },
    "network_binance": "tcp_ok_but_tls_failed:SSLZeroReturnError",
    "network_pypi": "reachable:200",
    "disk_free_gb": 18.45,
    "probed_at": "2026-09-20T17:46:39.121212+00:00"
  },
  "requirements": {
    "ARC-01": {
      "status": "CODE_VERIFIED",
      "tests": [
        "tests/unit/test_*"
      ],
      "evidence": "verify_report.j
