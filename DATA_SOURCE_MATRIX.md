# DATA_SOURCE_MATRIX — Appendix A (Generated)

_Generated: 2026-09-20T18:05:12.858367+00:00 from `config/sources.yaml` (single source of truth). Tags V=verified 2026-09-20, U=unverified/candidate. FBK-07 keyless-complete._

| Capability | Primary | Fallbacks (free, ranked) | Keyless? | Tag chain | Notes |
|---|---|---|---|---|---|
| CAP-01_registry | binance_um | bybit_linear, okx_swap, hyperliquid, gate, bitget | YES (FBK-07) | binance_um:V (GET /fapi/v1/exchangeInfo), bybit_linear:V (GET /v5/market/instruments-info?category=linear|inverse), okx_swap:V (GET /api/v5/public/instruments?instType=SWAP|FUTURES), hyperliquid:V (POST /info {"type":"meta"}), gate:V (GET /api/v4/futures/{settle}/contracts), bitget:U (mix-market contracts) |  |
| CAP-02_live_1m | binance_um | bybit_linear, okx_swap, hyperliquid | YES (FBK-07) | binance_um:V (WS <symbol>@kline_1m on /market), bybit_linear:V (WS kline), okx_swap:U (WS candle channel), hyperliquid:V (WS candle) |  |
| CAP-03_candle_rest | binance_um | bybit_linear, okx_swap, hyperliquid | YES (FBK-07) | binance_um:V (GET /fapi/v1/klines + markPriceKlines), bybit_linear:V (GET /v5/market/kline + mark-price-kline), okx_swap:V (GET /api/v5/market/candles + history-candles), hyperliquid:V (candleSnapshot) |  |
| CAP-04_bulk | data_binance_vision | public_bybit, bybit_rest, okx_rest | YES (FBK-07) | data_binance_vision:V (futures/um,futures/cm zips + checksums), public_bybit:V (https://public.bybit.com/), bybit_linear:V (REST-paged history), okx_swap:V (REST-paged history) |  |
| CAP-05_mark_funding | binance_um | bybit_linear, okx_swap, hyperliquid, coinalyze | YES (FBK-07) | binance_um:V (GET /fapi/v1/premiumIndex + /fapi/v1/fundingRate), bybit_linear:V (tickers + GET /v5/market/funding/history), okx_swap:V (public/funding-rate + funding-rate-history + mark-price), hyperliquid:V (metaAndAssetCtxs), coinalyze:V (funding-rate / predicted) |  |
| CAP-06_oi | binance_um | bybit_linear, okx_swap, hyperliquid, coinalyze | YES (FBK-07) | binance_um:V (GET /fapi/v1/openInterest + metrics + openInterestHist(30d)), bybit_linear:V (GET /v5/market/open-interest), okx_swap:V (public/open-interest + rubik open-interest-history), hyperliquid:V (metaAndAssetCtxs), coinalyze:V (open-interest + open-interest-history) |  |
| CAP-07_ratios_taker | binance_metrics | okx_swap, bybit, coinalyze, inhouse | YES (FBK-07) | binance_um:U (/futures/data/* ratios), okx_swap:V (rubik long-short + taker-volume), bybit_linear:U (account-ratio (probe)), coinalyze:U (long/short ratio history), inhouse:V (taker-buy volume from klines) |  |
| CAP-08_liquidations | binance_um | okx_swap, bybit_linear, hyperliquid, coinalyze | YES (FBK-07) | binance_um:V (WS forceOrder + liquidationSnapshot (CM only after 2024-03-31 UM ended)), okx_swap:V (GET /api/v5/public/liquidation-orders), bybit_linear:U (WS liquidation), hyperliquid:U (WS liquidation), coinalyze:V (liquidation history) |  |
| CAP-09_top_of_book | binance_um | bybit_linear, okx_swap, hyperliquid | YES (FBK-07) | binance_um:V (WS bookTicker on /public), bybit_linear:V (tickers WS/REST), okx_swap:V (tickers / BBO), hyperliquid:V (allMids + l2Book) |  |
| CAP-10_depth | binance_um | bybit_linear, okx_swap, hyperliquid | YES (FBK-07) | binance_um:V (depth streams /public diff+snapshot), bybit_linear:V (orderbook REST + WS), okx_swap:U (books/books5), hyperliquid:V (l2Book ≤20/side) |  |
| CAP-11_trades | binance_um | bybit_linear, okx_swap, hyperliquid | YES (FBK-07) | binance_um:V (WS @aggTrade + bulk aggTrades), bybit_linear:V (recent-trade + public.bybit.com), okx_swap:V (public trades REST/WS), hyperliquid:V (WS trades) |  |
| CAP-12_margin_tiers | binance_um | bybit_linear, okx_swap, hyperliquid | YES (FBK-07) | binance_um:U (exchangeInfo + leverage bracket (signed not keyless)), bybit_linear:V (GET /v5/market/risk-limit), okx_swap:V (GET /api/v5/public/position-tiers), hyperliquid:V (meta margin tiers) |  |
| CAP-14_time_sync | venue_time | ntp, http_date, other_venue | YES (FBK-07) | venue_time:V (GET /fapi/v1/time etc + OKX /api/v5/public/time), ntp:V (NTP pool (ntplib)), http_date:V (HTTP Date header), other_venue:V (other venue server time) |  |
| CAP-15_metadata | venue_registry | coinpaprika, coinlore, coingecko_demo, cmc | YES (FBK-07) | venue_registry:V (base + underlying type), coinpaprika:V (free 20k/month), coinlore:V (~1 req/s), coingecko_demo:V (10k/month 30/min), cmc:V (10k credits/month 333/day 30/min) |  |
| CAP-16_sentiment | alternative_me | cmc, inhouse, coinalyze | YES (FBK-07) | alternative_me:V (https://api.alternative.me/fng/), cmc:V (Fear & Greed), inhouse:V (composite volatility+breadth+funding+OI), coinalyze:V (funding/OI/liquidation proxy) |  |
| CAP-17_macro | seed_calendar | faireconomy, fred, official_pages | YES (FBK-07) | seed_calendar:V (config/macro_calendar_seed.yaml), faireconomy:U (ff_calendar_thisweek.json), fred:U (release calendar API), official_pages:U (Fed/BLS/BEA ICS) |  |
| CAP-18_news | rss_bundle | cryptopanic, gdelt, exchange_announcements, reddit | YES (FBK-07) | rss_bundle:V (CoinDesk,Cointelegraph,Decrypt,Bitcoinist,CryptoSlate,Bitcoin Magazine), cryptopanic:U, gdelt:U (DOC 2.0 API), exchange_announcements:U |  |
| CAP-20_notifications | desktop_toast | telegram, ntfy, discord, smtp | YES (FBK-07) | desktop_toast:U, telegram:U, ntfy:U, discord:U |  |

## Venues

| Venue | REST base | WS base | Limits | Tag |
|---|---|---|---|---|
| binance_um | https://fapi.binance.com | wss://fstream.binance.com | {'weight_per_min': 2400, 'streams_per_conn': 200, 'control_msgs_per_s': 10} | V |
| bybit_linear | https://api.bybit.com | wss://stream.bybit.com | {'requests_per_5s': 600, 'ws_per_5s': 500, 'market_conns_per_ip': 1000} | V |
| okx_swap | https://www.okx.com | wss://ws.okx.com:8443/ws/v5/public | — | V |
| hyperliquid | https://api.hyperliquid.xyz | wss://api.hyperliquid.xyz/ws | {'weight_per_min': 1200, 'conns': 10, 'new_conns_per_min': 30, 'subs': 1000} | V |

## Infrastructure fallbacks
- **database**: PostgreSQL → Portable PostgreSQL → SQLite WAL → DuckDB
- **messaging**: Postgres outbox + LISTEN/NOTIFY → SQLite polling → asyncio queue → NDJSON journal
- **archive**: Parquet+zstd+DuckDB → Parquet+Polars → Parquet+pandas → CSV.zst

## Candidate pool (replacements if a free source dies)

- Gate.io
- Bitget
- KuCoin Futures
- MEXC Futures
- BingX
- dYdX indexer
- Deribit

> Rule: never circumvent geo-block (INV-14/SEC-09). If primary returns 451/403 → status RESTRICTED, automatic failover after hysteresis (FBK-05). Every day `source_matrix_check` reprobes V/U (FBK-10).