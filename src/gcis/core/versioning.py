import hashlib, json
from pathlib import Path
from gcis import __version__, __analysis_version__

def evidence_hash(market_snapshot_ref: str, feature_snapshot_ref: str, config_version: str, analysis_version: str = __analysis_version__) -> str:
    payload = {
        "market_snapshot_ref": market_snapshot_ref,
        "feature_snapshot_ref": feature_snapshot_ref,
        "config_version": config_version,
        "analysis_version": analysis_version,
    }
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode()).hexdigest()

def compute_config_version(config_dict: dict) -> str:
    canon = json.dumps(config_dict, sort_keys=True, default=str)
    return hashlib.sha256(canon.encode()).hexdigest()[:16]
