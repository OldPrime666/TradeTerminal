# نقشه راه کامل GCIS 2026 — از صفر تا اجرا روی سیستم شما
> **نسخه 3.0 فیوچرز — همه قراردادها، فقط منابع رایگان با Failover**

این سند مرحله‌به‌مرحله به فارسی است. هر مرحله دقیقاً چه دستوری، چه خروجی و چه تصمیمی لازم دارد را می‌گوید. برای جزئیات فنی انگلیسی به `AGENTS.md`, `docs/SPEC.md`, `config/default.yaml`, `config/sources.yaml` مراجعه کنید.

---

## خلاصه معماری (چرا این طراحی؟)
- **همه قراردادهای فیوچرز** از رجیستری Venue (Binance UM → Bybit → OKX → Hyperliquid) کشف می‌شود — هیچ لیست ثابت `BTC,ETH...` وجود ندارد (INV-25).
- **فقط منابع رایگان:** هر قابلیت (کندل، funding، OI، liquidation، ... ) یک زنجیره `PRIMARY + ≥3 fallback رایگان` دارد (`config/sources.yaml` + `DATA_SOURCE_MATRIX.md`). بدون کلید هم کار می‌کند؛ با کلید رایگان شتاب می‌گیرد (FBK-07). هیچ bypass جغرافیایی مجاز نیست.
- **صداقت:** `NO DATA` / `NO TRADE` / `N/A`ِ صادق بهتر از عدد ساختگی است.
- **فیوچرز ایمن:** لوریج/مارجین/liquidation/funding همیشه مدل می‌شود (FUT).

---

## پیش‌نیاز سیستم شما (Windows 10/11 توصیه، Linux هم می‌شود)

| مورد | نسخه/مقدار | بررسی |
|------|-----------|--------|
| Python | **3.13.x** ترجیحاً؛ 3.12 یا 3.11.2 فعلی sandbox هم می‌شود (`UNVERIFIED_ENV` برای wheels 3.13) | `python --version` |
| `tzdata` | برای Windows | `pip show tzdata` |
| PostgreSQL | نسخه major پشتیبانی‌شده؛ یا SQLite fallback خودکار `var/gcis.db` | `psql --version` یا `pg_isready` |
| دیسک | ≥10GB آزاد | `df -h` |
| اینترنت | خروجی به `fapi.binance.com`, `api.bybit.com`, `www.okx.com`, `api.hyperliquid.xyz`, `data.binance.vision`, `public.bybit.com` (اگر بلاک بود → `NO DATA` صادق، نه کرش) | `scripts/env_probe.py` |

---

## مرحله 0 — کلون و نصب (5 دقیقه)

```bat
:: Windows
git clone https://github.com/OldPrime666/TradeTerminal.git
cd TradeTerminal
git checkout arena/01a0bfdc-tradeterminal

install.bat
:: - pip upgrade + نصب از pyproject.toml (پین دقیق، هش)
:: - ساخت var/archive,var/raw,logs
:: - اجرای preflight (گزارش می‌دهد کدام Venue reachable/restricted)
```
```bash
# Linux / WSL / sandbox
./install.sh
# معادل: pip install -e .  + mkdir -p var/... + python -m gcis.cli preflight
```

**خروجی مورد انتظار `install.bat`:**
```
[GCIS] Installing...
Config loaded mode=PAPER db=sqlite:///var/gcis.db
DB reachable: OK
Timezone DB: OK
Disk free 18 GB
Binance UM fapi.binance.com reachable (یا RESTRICTED_451 → فیلوور فعال، honest)
Preflight done
```

اگر `RESTRICTED_451` دیدید → **فیلوور خودکار** به Bybit (بنر `VENUE_FALLBACK_ACTIVE` در UI). هرگز VPN/proxy نزنید.

---

## مرحله 1 — آشکارسازی محیط (1 دقیقه)

```bash
python scripts/env_probe.py
# یا
python -m gcis.cli preflight
cat BUILD_STATE.json | grep -A 15 '"environment"'
```

این فایل را به‌روز می‌کند:
```json
"network_venues": {
  "binance_um": "reachable:200",
  "bybit": "reachable:200",
  "okx": "reachable:200",
  "hyperliquid": "reachable:200",
  "data_binance_vision": "reachable",
  "coinpaprika": "reachable"
}
```
اگر همه `unreachable` → UI تا برگشت شبکه `NO DATA` می‌ماند (درست).

**بررسی Fallback-matrix:**
```bash
python scripts/source_matrix_check.py   # هر entry را live probe می‌کند، V/U را به‌روز می‌کند
cat DATA_SOURCE_MATRIX.md
```

---

## مرحله 2 — اجرای ترمینال (30 ثانیه)

```bat
start.bat
:: → streamlit run src/gcis/app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
:: مرورگر: http://127.0.0.1:8501  (PAPER mode)
```

```bash
./start.sh  # در sandbox → 0.0.0.0:8501 (پیش‌نمایش 8501-....e2b.app)
```

**بنر بالای UI چی باید ببینید (UIX-04):**
- `◈ GLOBALCRYPTOICTSCANNER 2026 | v0.1.1 | PAPER | Data: HEALTHY/DEGRADED | DB: OK | Transport: WEBSOCKET/POLLING`
- **Coverage:** `analysed 427 / listed 512 · warming 12 · excluded 3 (EXCLUDED_ASSET_CLASS) ...` (DAT-19)
- اگر فیلوور: `VENUE_FALLBACK_ACTIVE: binance_um → bybit_linear`

**منوی کناری (بدون لیست ثابت!):**
- `Market / Contract` از `contract_registry` پر می‌شود (دینامیک). وقتی خالی است: `— (registry warming up)` — نشانه INV-25 پاس است.

---

## مرحله 3 — تایید سلامت (1 دقیقه)

```bat
healthcheck.bat
:: یا
python -m gcis.cli healthcheck
```

خروجی JSON `{"verdict":"HEALTHY","details":{"db_ok":true,"providers":{...}}}` باید 0 برگرداند.

**Verify (اثبات):**
```bash
python -m gcis.cli verify --quick
# چک‌ها: invariant scanner (9/9 OK), config_load, db_migrations, pytest 16 passed
# → verify_report.json + docs/audit/P00/verify_report.json

python -m gcis.cli verify --full      # fault-injection + replay
python -m gcis.cli verify --post-install  # 60s live data flowing + یک کندل بسته هر تایم‌فریم
python scripts/check_invariants.py    # INV-01..26, SEC-09
```

در sandbox چون Binance TLS بلاک است → تیکه‌های live `UNVERIFIED_ENV` می‌شوند (صادق، نه fail).

---

## مرحله 4 — پر کردن تاریخچه (بسته به دیسک و پهنای باند)

**اتومات (پیشنهاد): سیستم خودش از `data.binance.vision` و `public.bybit.com` دانلود می‌کند:**

```bash
python -m gcis.cli download-history --venue binance_um --timeframe 1m
# در背后: ماهانه ZIPها + روزانه tail + REST امروز، نرمال‌سازی ms/µs، اشتقاق تایم‌فریم‌های بالاتر از 1m (ARC-20a)، Parquet در var/archive، گزارش gap
```

**دستی (برای تست سریع):** فقط چند قرارداد liquid:
```bash
python -m gcis.cli download-history --symbols BTCUSDT ETHUSDT --timeframe 1m
```

نتیجه: `var/archive/*.parquet` + `archive_segments` + گزارش `coverage/gap`.

**نکته v3:** فقط `1m` ذخیره ingest می‌شود؛ `5m,15m,1h,4h,1d` از `1m` بسته مشتق می‌شوند (6× سبک‌تر برای صدها قرارداد). تطبیق با کندل venue هر بار چک می‌شود (`AGGREGATION_MISMATCH`).

---

## مرحله 5 — اجرای Live Ingestion (اختیاری ولی پیشنهادی)

به‌صورت خودکار توسط `supervisor` (4 پروسه: ingest/core/slow/ui) با شاردینگ:
- هر قرارداد یک `kline_1m` stream → شارد روی `ceil(N/180)` کانکشن (Binance 200/stream حد)
- گروه `all_market` (mark/funding/bookTicker/liquidations) — چند stream برای همه قراردادها
- گروه `focus_set` (depth/aggTrade) فقط برای قراردادهای با پوزیشن/سیگنال فعال (ARC-20f)

**بررسی:**
- UI → System Health → `ingest: HEALTHY`, `subscription ledger = registry`
- `python -m gcis.cli healthcheck` → `candle_freshness: HEALTHY`, `analysed_live/listed ≥0.98` (یا `ANALYSIS_LAG` هشدار)

اگر بسته باندل >20s طول کشید → `ANALYSIS_LAG` صریح، هیچ قراردادی بی‌صدا حذف نمی‌شود.

---

## مرحله 6 — تحقیق (بدون پول)

```bash
python -m gcis.cli census
# → docs/reports/SIGNAL_CENSUS_*.md  (TIER_POOLED_ONLY / TIER_STRATEGY / NONE) که نوع پولینگ احتمال را تعیین می‌کند

python -m gcis.cli backtest --venue binance_um --timeframe 15m
# 4 بیس‌لاین: random-entry, buy-and-hold, EMA-cross, time-shift + verdict EDGE vs BASELINE
```

همه backtestها `OHLC_APPROXIMATION` یا `INTRABAR_REPLAY` + `DEGRADED_DATA_TEST` اگر mark/funding ناقص (FUT).

---

## مرحله 7 — نقشه راه فازها (چطور پروژه «کامل» می‌شود)

| فاز | هدف (خلاصه) | ورودی شما |
|-----|-------------|-----------|
| **P00** ✅ CODE_VERIFIED | اسکلت، env_probe همه venues، config/sources، DB، health، ورِفای | تمام شد (sandbox) |
| **P01** IN_PROGRESS | **Registry دینامیک Binance UM/CM** → بدون لیست ثابت، asset_class، coverage skeleton | `preflight` باید 1 قرارداد واقعی بیاورد یا `NO DATA` صادق |
| **P02** | Bulk loader v3 (1m + mark/premium/funding، اشتقاق HTF، fallback bybit) | دیسک 200GB budget |
| **P03** | Live شاردینگ همه قراردادها + subscription ledger + raw recorder | تست با 1000 synthetic قرارداد |
| **P04** | **Failover controller** + آداپتورهای Bybit/OKX/Hyperliquid (registry, candles, mark/funding/OI, margin) + drill `failover_drill.py` | `source_matrix_check --assert-min-fallbacks 3` باید سبز شود |
| **P05** | اندیکاتورها، regime، MarketView، Universe Scanner, market-wide context | تست علیّت |
| **P06** | ICT (swings, BOS/CHOCH, FVG, OB, sweeps...) + تست golden/no-repaint |  |
| **P07** | استراتژی ICT-A Long/Short + gates/fusion + storm handling + Outcome Tracker |  |
| **P08** | ریسک فیوچرز (لوریج/لیکویید/فاندینگ) + Paper execution + lifecycle قرارداد | تست liquidation روی مثال‌های Venue |
| **P09** | Backtest universe-scale + baselines + census |  |
| **P10** | Runtime supervisor + health + coverage/lag monitor | soak 30m live |
| **P11** **M0 v0.1** | UI خواندنی کامل (coverage page، health, contracts, signals, kill switch) + `.bat` | `verify --post-install` سبز روی Windows واقعی |
| **P12–P22** | ترمینال کامل، walk-forward، derivatives overlays، probability, hardening, focus-set depth, news, notifications, DOM/scalping, Live testnet, ... | هر فاز DoD 11.0 |

**قانون:** هیچ فازی با <3 fallback آزاد برای قابلیت‌هایش `CODE_VERIFIED` نمی‌شود (FBK-01). فازهای P12+ تا P11 تمام نشده شروع نمی‌شود.

---

## چک‌لیست نهایی “Deployed” روی سیستم شما (0.8)

- [ ] `install.bat` سبز (یا `install.sh`)
- [ ] `start.bat` → UI `http://127.0.0.1:8501` با داده واقعی فیوچرز برای **کل** universe + بنر `analysed/listed` صادق
- [ ] `healthcheck.bat` → `HEALTHY`
- [ ] `verify.bat --post-install` سبز (در sandbox: بخش live `UNVERIFIED_ENV` صادق است)
- [ ] اگر Binance 451 → بنر `VENUE_FALLBACK_ACTIVE` + warm-up خودکار؛ هرگز VPN نزنید

بالاترین وضعیتی که یک Agent می‌تواند ادعا کند: `M0 CODE COMPLETE — EMPIRICAL VALIDATION PENDING`. `PRODUCTION READY` فقط پس از گزارش Live Readiness با شواهد هفته‌ها Paper.

---

## عیب‌یابی سریع

| علامت | معنی | کار |
|-------|------|-----|
| `NO DATA` همه‌جا | همه Venueها unreachable | `env_probe.py` را دوباره بزنید؛ اینترنت را چک کنید |
| `VENUE_FALLBACK_ACTIVE` | primary بلاک/خراب | صبر کنید؛ warm-up 500 بار per timeframe از Venue جدید |
| `ANALYSIS_LAG` / `NOT_SUBSCRIBED` | لود زیاد | فوکوس‌ست را کم کنید، `bundle_latency_budget_s` را بالا ببرید (نیاز سخت‌افزار) |
| `LIQUIDATION_BUFFER_INSUFFICIENT` | استاپ نزدیک لیکویید | لوریج را کم کنید یا استاپ را بازتر کنید (FUT-03) |
| `CODE_VERIFIED` نشد | تست fail | خروجی `verify_report.json` را باز کنید؛ `scripts/check_invariants.py` را بخوانید |

---

## منابع رایگان (چرا بدون کلید کار می‌کند)

کل ماتریس در `config/sources.yaml` و `DATA_SOURCE_MATRIX.md` است. هر قابلیت ≥3 جایگزین رایگان دارد:
- **Market:** Binance UM/CM, Bybit, OKX, Hyperliquid, Gate, Bitget + `data.binance.vision` و `public.bybit.com` (آرشیو) + Coinalyze (کی‌دِ اختیاری)
- **متادیتا/سنتمنت/ماکرو/نیوز:** CoinPaprika, CoinLore, CoinGecko Demo, CMC Basic (همه با سهم رایگان), Alternative.me Fear&Greed, FRED, RSS (CoinDesk...) — همه بدون اجبار کلید؛ اگر key خالی باشد زنجیره با اعضای `auth:false` ادامه می‌دهد (FBK-07).

---

## دستورات مرجع

```bash
python -m gcis.cli preflight              # self-check همه venues + registry + coverage
python -m gcis.cli healthcheck
python -m gcis.cli verify --quick|full|post-install
python -m gcis.cli download-history
python -m gcis.cli backtest
python -m gcis.cli census
python scripts/env_probe.py
python scripts/check_invariants.py
python scripts/source_matrix_check.py --generate-md
python scripts/failover_drill.py          # تمام faultهای FBK-10
python scripts/replay_verify.py           # 20 سیگنال تصادفی، evidence_hash
```

**امنیت:** UI فقط `127.0.0.1`، XSRF روشن، اسرار فقط در `.env` (هرگز در Git/DB/Log). هیچ مسیری برای دور زدن محدودیت جغرافیایی وجود ندارد (SEC-09).

---
*مستندات صادق > زیبایی. “No edge found” یک نتیجه معتبر است.*
