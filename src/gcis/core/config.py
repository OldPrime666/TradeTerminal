from pathlib import Path
import yaml
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_YAML = ROOT / "config" / "default.yaml"

class Settings(BaseSettings):
    app_name: str = Field(default="GLOBALCRYPTOICTSCANNER 2026")
    app_mode: str = Field(default="PAPER")
    enable_live_trading: bool = Field(default=False)
    database_url: str = Field(default="sqlite:///var/gcis.db")
    exchange_rest_base: str = Field(default="https://data-api.binance.vision")
    exchange_ws_base: str = Field(default="wss://data-stream.binance.vision")
    bind_address: str = Field(default="127.0.0.1")

    model_config = {"env_prefix": "GCIS_", "env_file": ".env", "extra": "allow"}

    @field_validator("app_mode")
    @classmethod
    def validate_mode(cls, v):
        if v not in ("RESEARCH","PAPER","LIVE"):
            raise ValueError("app_mode must be RESEARCH/PAPER/LIVE")
        return v

def load_yaml_config(path: Path = DEFAULT_YAML) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data

def load_config() -> dict:
    yaml_cfg = load_yaml_config()
    env_cfg = Settings()
    # merge: yaml_cfg base, with env overrides
    merged = yaml_cfg.copy()
    # inject env relevant
    merged.setdefault("app", {})["mode"] = env_cfg.app_mode
    merged.setdefault("app", {})["enable_live_trading"] = env_cfg.enable_live_trading
    merged.setdefault("database", {})["url"] = env_cfg.database_url
    merged.setdefault("exchange", {})["binance_rest_base"] = env_cfg.exchange_rest_base
    merged.setdefault("exchange", {})["binance_ws_base"] = env_cfg.exchange_ws_base
    merged.setdefault("ui", {})["bind_address"] = env_cfg.bind_address
    # hard caps enforcement
    # risk_per_trade_pct must be <=0.5
    try:
        rpt = merged.get("risk", {}).get("risk_per_trade_pct", 0.25)
        if float(rpt) > 0.5 + 1e-9:
            raise ValueError(f"risk_per_trade_pct {rpt} exceeds HARD cap 0.50")
        mdl = merged.get("risk", {}).get("max_daily_loss_pct", 1.5)
        if float(mdl) > 2.0 + 1e-9:
            raise ValueError(f"max_daily_loss_pct {mdl} exceeds HARD cap 2.0")
        mtd = merged.get("risk", {}).get("max_trades_per_day", 6)
        if int(mtd) > 10:
            raise ValueError(f"max_trades_per_day {mtd} exceeds HARD cap 10")
    except (ValueError, TypeError) as e:
        if "exceeds HARD cap" in str(e):
            raise
    return merged

# singleton
_config_cache: dict | None = None

def get_config() -> dict:
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache

def reload_config() -> dict:
    global _config_cache
    _config_cache = load_config()
    return _config_cache

def get_version_info() -> dict:
    from gcis import __version__, __analysis_version__
    import hashlib, json
    cfg = get_config()
    # canonical json of config without secrets
    canon = json.dumps(cfg, sort_keys=True, default=str)
    sha = hashlib.sha256(canon.encode()).hexdigest()[:16]
    return {"software_version": __version__, "analysis_version": __analysis_version__, "config_hash": sha}
