from dataclasses import dataclass
from typing import Optional, List
from decimal import Decimal

@dataclass
class StrategyResult:
    strategy_name: str
    strategy_version: str
    eligible: bool
    direction: Optional[str]  # LONG SHORT None
    setup_score: int
    confidence: float
    regime_compatibility: bool
    entry_zone: Optional[tuple]  # (low, high)
    invalidation: Optional[Decimal]
    targets: Optional[list]
    evidence: List[str]
    reason_codes: List[str]
    required_data: List[str]
    data_quality: str
