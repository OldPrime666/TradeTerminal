from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict

HARD_RISK_PER_TRADE_PCT = Decimal("0.50")
HARD_DAILY_LOSS_PCT = Decimal("2.0")
HARD_MAX_TRADES_PER_DAY = 10
HARD_MAX_LEVERAGE = Decimal("10")
HARD_MAX_EFFECTIVE_LEVERAGE = Decimal("10")

class RiskManager:
    def __init__(self, config: dict):
        self.config = config

    def check(self, intent: dict, daily_state: dict, open_risk_pct: float, kill_switch: bool, exposure: dict) -> dict:
        """
        Returns RiskCheckResult dict: allowed, reason_code, etc.
        Enforces INV-09 hard caps and Part12 defaults.
        is_close intent bypasses new-entry blocks (RSK-06 separate close).
        """
        # Close intents allowed even if kill active / daily lock (separate command)
        if intent.get("is_close"):
            # still enforce hard caps not relevant for close? allow
            return {"allowed": True, "reason_code": None, "detail": "close allowed despite kill/daily lock"}
        reason = None
        risk_cfg = self.config.get("risk",{})
        risk_pct = Decimal(str(risk_cfg.get("risk_per_trade_pct", 0.25)))
        if risk_pct > HARD_RISK_PER_TRADE_PCT:
            return {"allowed": False, "reason_code": "HARD_CAP_RISK_PER_TRADE", "detail": f"{risk_pct} > {HARD_RISK_PER_TRADE_PCT}"}
        daily_loss_pct = risk_cfg.get("max_daily_loss_pct", 1.5)
        max_trades = risk_cfg.get("max_trades_per_day", 6)
        if Decimal(str(daily_loss_pct)) > HARD_DAILY_LOSS_PCT:
            return {"allowed": False, "reason_code": "HARD_CAP_DAILY_LOSS", "detail": f"{daily_loss_pct}"}
        if max_trades > HARD_MAX_TRADES_PER_DAY:
            return {"allowed": False, "reason_code": "HARD_CAP_TRADES", "detail": f"{max_trades}"}
        if kill_switch:
            return {"allowed": False, "reason_code": "KILL_SWITCH_ACTIVE"}
        if daily_state.get("risk_lock") == "BLOCK_NEW_TRADES":
            return {"allowed": False, "reason_code": "RISK_LIMIT", "detail": "daily loss lock"}
        if daily_state.get("trades_today",0) >= max_trades:
            return {"allowed": False, "reason_code": "RISK_LIMIT", "detail": "max trades per day"}
        # concurrent positions
        max_concurrent = risk_cfg.get("max_concurrent_positions", 3)
        if exposure.get("open_positions",0) >= max_concurrent:
            return {"allowed": False, "reason_code": "RISK_LIMIT", "detail": "max concurrent positions"}
        # aggregate open worst-case risk
        max_open_risk = risk_cfg.get("max_open_worst_case_risk_pct", 1.5)
        # we keep as float
        if open_risk_pct >= max_open_risk:
            return {"allowed": False, "reason_code": "RISK_LIMIT", "detail": "max open worst-case risk"}
        # per symbol
        per_symbol = risk_cfg.get("max_per_symbol_risk_pct", 0.5)
        if exposure.get("per_symbol_risk",0) >= per_symbol:
            return {"allowed": False, "reason_code": "RISK_LIMIT", "detail": "per symbol risk"}
        # leverage caps (INV-09, FUT-02)
        lev_cap = Decimal(str(risk_cfg.get("max_leverage_cap", 3)))
        eff_cap = Decimal(str(risk_cfg.get("max_effective_leverage", 3)))
        if lev_cap > HARD_MAX_LEVERAGE:
            return {"allowed": False, "reason_code": "HARD_CAP_LEVERAGE", "detail": f"{lev_cap} > {HARD_MAX_LEVERAGE}"}
        if eff_cap > HARD_MAX_EFFECTIVE_LEVERAGE:
            return {"allowed": False, "reason_code": "HARD_CAP_EFFECTIVE_LEVERAGE"}
        intent_lev = Decimal(str(intent.get("leverage", 3)))
        if intent_lev > lev_cap + Decimal("1e-9"):
            return {"allowed": False, "reason_code": "LEVERAGE_EXCEEDS_CAP", "detail": f"{intent_lev} > {lev_cap}"}
        # effective leverage
        gross_notional = Decimal(str(exposure.get("gross_notional", 0))) + Decimal(str(intent.get("notional", 0)))
        equity = Decimal(str(daily_state.get("current_equity", 10000)))
        if equity > 0 and gross_notional / equity > eff_cap + Decimal("1e-9"):
            return {"allowed": False, "reason_code": "LEVERAGE_EXCEEDS_CAP", "detail": f"effective {gross_notional/equity:.2f}x > {eff_cap}x"}
        # liquidation buffer (FUT-03)
        # require |entry-stop| <= 0.5 * |entry - liq| and |stop-liq| >=1 ATR
        liq = intent.get("liquidation_price")
        entry = intent.get("entry")
        stop = intent.get("stop")
        atr = intent.get("atr")
        if liq and entry and stop and atr:
            try:
                liq_d = abs(Decimal(str(entry)) - Decimal(str(liq)))
                stop_d = abs(Decimal(str(entry)) - Decimal(str(stop)))
                if liq_d > 0 and stop_d > liq_d * Decimal("0.5"):
                    return {"allowed": False, "reason_code": "LIQUIDATION_BUFFER_INSUFFICIENT"}
                if abs(Decimal(str(stop)) - Decimal(str(liq))) < Decimal(str(atr)) * Decimal("1.0"):
                    return {"allowed": False, "reason_code": "LIQUIDATION_BUFFER_INSUFFICIENT"}
            except: pass
        # funding too costly
        exp_funding = intent.get("expected_funding_bps", 0)
        if exp_funding > 15:  # 15% of R proxy
            return {"allowed": False, "reason_code": "FUNDING_TOO_COSTLY"}
        # spread lock
        if intent.get("spread_bps",0) > risk_cfg.get("locks",{}).get("max_spread_bps",15):
            return {"allowed": False, "reason_code": "EXECUTION_UNSAFE", "detail": "spread too high"}
        equity = Decimal(str(daily_state.get("current_equity", 10000)))
        risk_amount = equity * (risk_pct/Decimal(100))
        return {"allowed": True, "reason_code": None, "risk_amount": float(risk_amount), "risk_percent": float(risk_pct)}
